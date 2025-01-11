"""
Handle all media collection related functions
"""

import logging
import os
import shutil
from pathlib import Path
from threading import Lock
from uuid import UUID, uuid4

from sqlalchemy import delete, func, select
from sqlalchemy.exc import NoResultFound
from sqlalchemy.orm import Session

from .. import CACHE_PATH, PATH_PROCESSED, PATH_UNPROCESSED, RECYCLE_PATH
from ..database.database import engine
from ..database.models import DimensionTypes, V3CachedItem, V3Mediaitem
from ..database.schemas import MediaitemPublic
from .baseservice import BaseService
from .config import appconfig
from .mediacollection.resizer import MAP_DIMENSION_TO_PIXEL, generate_resized
from .sseservice import SseEventDbInsert, SseEventDbRemove, SseService

logger = logging.getLogger(__name__)


class MediacollectionService(BaseService):
    """Handle all image related stuff"""

    def __init__(self, sse_service: SseService):
        super().__init__(sse_service=sse_service)

        self._lock_cache_check: Lock = Lock()

        # don't access database during init because it might not be set up during tests...

    def start(self):
        super().start()
        # remove outdated items from cache during startup.
        self._cache_clear_outdated()
        self._logger.info(f"initialized DB, found {self.get_number_of_images()} images")
        super().started()

    def stop(self):
        super().stop()
        pass
        super().stopped()

    def db_add_item(self, item: V3Mediaitem):
        with Session(engine) as session:
            session.add(item)
            session.commit()
            session.refresh(item)

            # and insert in client db collection so gallery is up to date.
            if item.show_in_gallery:
                self._sse_service.dispatch_event(SseEventDbInsert(mediaitem=MediaitemPublic.model_validate(item)))

            return item.id

    def db_update_item(self, item: V3Mediaitem):
        with Session(engine) as session:
            session.add(item)
            session.commit()
            session.refresh(item)

    def _db_delete_item_by_item(self, item: V3Mediaitem):
        with Session(engine) as session:
            session.delete(item)
            session.commit()

            # # and remove from client db collection so gallery is up to date.
            # event is even sent if not show_in_gallery, client needs to sort things out
            self._sse_service.dispatch_event(SseEventDbRemove(mediaitem=MediaitemPublic.model_validate(item)))

    def _db_delete_items(self):
        with Session(engine) as session:
            statement = delete(V3Mediaitem)
            result = session.execute(statement)
            session.commit()

            logger.info(f"deleted {result.rowcount} items from the database")

    def get_number_of_images(self) -> int:
        with Session(engine) as session:
            statement = select(func.count(V3Mediaitem.id))
            return session.scalars(statement).one()

    def db_get_all_jobitems(self, job_identifier: UUID) -> list[V3Mediaitem]:
        with Session(engine) as session:
            galleryitems = session.scalars(
                select(V3Mediaitem).order_by(V3Mediaitem.created_at.desc()).where(V3Mediaitem.job_identifier == job_identifier)
            ).all()

            return galleryitems

    def db_get_images(self, offset: int = 0, limit: int = 500) -> list[V3Mediaitem]:
        with Session(engine) as session:
            galleryitems = session.scalars(select(V3Mediaitem).order_by(V3Mediaitem.created_at.desc()).offset(offset).limit(limit)).all()

            return galleryitems

    def db_get_most_recent_mediaitem(self) -> V3Mediaitem:
        try:
            with Session(engine) as session:
                return session.scalars(select(V3Mediaitem).order_by(V3Mediaitem.created_at.desc())).first()
        except NoResultFound as exc:
            raise FileNotFoundError("could get an item") from exc

    def db_get_image_by_id(self, item_id: UUID) -> V3Mediaitem:
        if not isinstance(item_id, UUID):
            raise RuntimeError("item_id is wrong type")

        try:
            with Session(engine) as session:
                results = session.scalars(select(V3Mediaitem).where(V3Mediaitem.id == item_id))
                item = results.one()

                if not item.unprocessed.exists() or not item.processed.exists():
                    raise FileNotFoundError(f"cannot find representing file for item {item_id}!")

                return item
        except NoResultFound as exc:
            raise FileNotFoundError(f"could not find {item_id} in database") from exc

    def delete_image_by_id(self, item_id: UUID):
        """delete single file and it's related thumbnails"""
        if not isinstance(item_id, UUID):
            raise RuntimeError("item_id is wrong type")

        self._logger.info(f"request delete item id {item_id}")

        try:
            # lookup item in collection
            item = self.db_get_image_by_id(item_id)
            self._logger.debug(f"found item={item}")

            # remove from collection
            self._db_delete_item_by_item(item)

            # remove files from disk
            self.delete_mediaitem_files(item)

            self._logger.debug(f"deleted mediaitem from db and files {item}")
        except Exception as exc:
            self._logger.error(f"error deleting item id={item_id}")
            raise exc

    def delete_mediaitem_files(self, mediaitem: V3Mediaitem):
        """delete single file and it's related thumbnails"""

        self._logger.info(f"request delete files of {mediaitem}")

        try:
            if appconfig.common.users_delete_to_recycle_dir:
                self._logger.info(f"moving {mediaitem} to recycle directory")
                shutil.move(mediaitem.unprocessed, Path(RECYCLE_PATH, mediaitem.unprocessed.name))
            else:
                os.remove(mediaitem.unprocessed)
        except FileNotFoundError:
            logger.warning(f"file {mediaitem.unprocessed} not found but ignore because shall be deleted anyways.")
        except Exception as exc:
            self._logger.exception(exc)
            raise RuntimeError(f"error deleting files for item {mediaitem}") from exc

        for file in [
            mediaitem.processed,
        ]:
            try:
                os.remove(file)
            except FileNotFoundError:
                logger.warning(f"file {file} not found but ignore because shall be deleted anyways.")
            except Exception as exc:
                self._logger.exception(exc)
                raise RuntimeError(f"error deleting files for item {mediaitem}") from exc

        self._logger.info(f"deleted files of {mediaitem}")

    def delete_all_mediaitems(self):
        """delete all images, inclusive thumbnails, ..."""
        try:
            self._db_delete_items()

            for file in Path(f"{PATH_UNPROCESSED}").glob("*.*"):
                os.remove(file)
            for file in Path(f"{PATH_PROCESSED}").glob("*.*"):
                os.remove(file)

        except Exception as exc:
            self._logger.exception(exc)
            raise exc

        self._logger.info("deleted all mediaitems")

    def _cache_clear_outdated(self):
        with Session(engine) as session:
            statement = select(V3CachedItem).join(V3Mediaitem).where(V3Mediaitem.updated_at > V3CachedItem.created_at)
            results = session.scalars(statement)
            outdated_items = results.all()

            for outdated_item in outdated_items:
                session.delete(outdated_item)

            session.commit()

            logger.info(f"deleted {len(outdated_items)} outdated items from the cache")

    def _cache_clear_all(self):
        with Session(engine) as session:
            statement = delete(V3CachedItem)
            session.execute(statement)
            session.commit()

    def _check_cache_valid(self, mediaitem_id: UUID, dimension: DimensionTypes, processed: bool = True):
        with Session(engine) as session:
            results = session.scalars(
                select(V3CachedItem)
                .join(V3Mediaitem)
                .where(V3CachedItem.v3mediaitem_id == mediaitem_id, V3CachedItem.dimension == dimension, V3CachedItem.processed == processed)
                .where(V3Mediaitem.updated_at < V3CachedItem.created_at)  # cached item created later than last updated mediaitem
            )

            v3cacheditem_exists = results.one_or_none()  # if none, there is no item yet cached and cached version needs to be created.

            # check files also, otherwise delete the item:
            if v3cacheditem_exists and not v3cacheditem_exists.filepath.exists():
                logger.warning("deleting cached item from DB because file representation does not exist any more.")
                session.execute(delete(v3cacheditem_exists))
                session.commit()

                return None

            return v3cacheditem_exists

    def get_mediaitem_file(self, mediaitem_id: UUID, dimension: DimensionTypes, processed: bool = True) -> Path:
        dimension_pixel = MAP_DIMENSION_TO_PIXEL.get(dimension, None)

        if dimension_pixel is None:
            raise ValueError(f"invalid dimension given: '{dimension}'")

        with Session(engine) as session:
            # if there are multiple requests for same item at the same time,
            # it might lead to generate cached versions multiple times wasting cpu until it's done.
            # so it's locked from the moment it's checked but that means there is only one process
            # at a time. Maybe a queue is more efficient, but it's ok for now probably.
            with self._lock_cache_check:
                v3cacheditem_exists = self._check_cache_valid(mediaitem_id, dimension, processed)

                if v3cacheditem_exists:
                    return v3cacheditem_exists.filepath

                else:
                    item = self.db_get_image_by_id(mediaitem_id)

                    id = uuid4()
                    v3cacheditem_new = V3CachedItem(
                        id=id,
                        v3mediaitem_id=mediaitem_id,
                        dimension=dimension,
                        processed=processed,
                        filepath=Path(CACHE_PATH, id.hex).with_suffix(item.unprocessed.suffix),
                    )

                    generate_resized(
                        filepath_in=item.processed if processed else item.unprocessed,
                        filepath_out=v3cacheditem_new.filepath,
                        scaled_min_length=dimension_pixel,
                    )

                    session.add(v3cacheditem_new)
                    session.commit()

                    return v3cacheditem_new.filepath
