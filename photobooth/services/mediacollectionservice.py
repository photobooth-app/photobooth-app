"""
Handle all media collection related functions
"""

import logging
import os
import shutil
from pathlib import Path
from uuid import UUID

from sqlalchemy.exc import NoResultFound
from sqlmodel import Session, delete, func, select

from .. import PATH_PROCESSED, PATH_UNPROCESSED
from ..database.database import engine
from ..database.models import DimensionTypes, V3Mediaitem, V3MediaitemPublic
from ..services.mediaprocessing.resizer import MAP_DIMENSION_TO_PIXEL, get_resized_filepath
from .baseservice import BaseService
from .config import appconfig
from .sseservice import SseEventDbInsert, SseEventDbRemove, SseService

logger = logging.getLogger(__name__)

RECYCLE_DIR = "recycle"


class MediacollectionService(BaseService):
    """Handle all image related stuff"""

    def __init__(self, sse_service: SseService):
        super().__init__(sse_service=sse_service)

        # ensure data directories exist
        os.makedirs(f"{RECYCLE_DIR}", exist_ok=True)

        self._logger.info(f"initialized DB, found {self.get_number_of_images()} images")

    def db_add_item(self, item: V3Mediaitem):
        with Session(engine) as session:
            session.add(item)
            session.commit()
            session.refresh(item)

            # and insert in client db collection so gallery is up to date.
            if item.show_in_gallery:
                self._sse_service.dispatch_event(SseEventDbInsert(mediaitem=V3MediaitemPublic.model_validate(item)))

            return item.id

    def _db_delete_item_by_item(self, item: V3Mediaitem):
        with Session(engine) as session:
            session.delete(item)
            session.commit()

            # # and remove from client db collection so gallery is up to date.
            # event is even sent if not show_in_gallery, client needs to sort things out
            self._sse_service.dispatch_event(SseEventDbRemove(mediaitem=V3MediaitemPublic.model_validate(item)))

    def _db_delete_items(self):
        with Session(engine) as session:
            statement = delete(V3Mediaitem)
            result = session.exec(statement)
            session.commit()

            logger.info(f"deleted {result.rowcount} items from the database")

    def get_number_of_images(self) -> int:
        with Session(engine) as session:
            statement = select(func.count(V3Mediaitem.id))
            results = session.exec(statement)
            count = results.one()

            return count

    def db_get_all_jobitems(self, job_identifier: UUID) -> list[V3Mediaitem]:
        with Session(engine) as session:
            galleryitems = session.exec(
                select(V3Mediaitem).order_by(V3Mediaitem.created_at.desc()).where(V3Mediaitem.job_identifier == job_identifier)
            ).all()

            return galleryitems

    def db_get_images(self, offset: int = 0, limit: int = 500) -> list[V3Mediaitem]:
        with Session(engine) as session:
            galleryitems = session.exec(select(V3Mediaitem).order_by(V3Mediaitem.created_at.desc()).offset(offset).limit(limit)).all()

            return galleryitems

    def db_get_most_recent_mediaitem(self) -> V3Mediaitem:
        try:
            with Session(engine) as session:
                return session.exec(select(V3Mediaitem).order_by(V3Mediaitem.created_at.desc())).first()
        except NoResultFound as exc:
            raise FileNotFoundError("could get an item") from exc

    def db_get_image_by_id(self, item_id: UUID) -> V3Mediaitem:
        if not isinstance(item_id, UUID):
            raise RuntimeError("item_id is wrong type")

        try:
            with Session(engine) as session:
                results = session.exec(select(V3Mediaitem).where(V3Mediaitem.id == item_id))

                return results.one()
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
                shutil.move(mediaitem.unprocessed, Path(RECYCLE_DIR, mediaitem.unprocessed.name))
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

    def get_mediaitem_file(self, mediaitem_id: UUID, dimension: DimensionTypes, processed: bool = True):
        item = self.db_get_image_by_id(mediaitem_id)

        dimension_pixel = MAP_DIMENSION_TO_PIXEL.get(dimension, 100)
        resized_filepath = get_resized_filepath(item.processed if processed else item.unprocessed, dimension_pixel)

        return resized_filepath
