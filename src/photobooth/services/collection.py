"""
Handle all media collection related functions
"""

import logging
import shutil
from pathlib import Path
from threading import Lock
from typing import cast
from uuid import UUID, uuid4

from sqlalchemy import CursorResult, delete, func, select
from sqlalchemy.exc import NoResultFound
from sqlalchemy.orm import Session

from .. import CACHE_PATH, PATH_CAMERA_ORIGINAL, PATH_PROCESSED, PATH_UNPROCESSED, RECYCLE_PATH, TMP_PATH
from ..appconfig import appconfig
from ..database.database import engine
from ..database.models import Cacheditem, DimensionTypes, Mediaitem
from ..database.schemas import MediaitemPublic
from ..plugins import pm as pluggy_pm
from ..utils.media_resizer import resize
from ..utils.metrics_timer import MetricsTimer
from .base import BaseService
from .sse import sse_service
from .sse.sse_ import SseEventDbInsert, SseEventDbRemove, SseEventDbUpdate

logger = logging.getLogger(__name__)


MAP_DIMENSION_TO_PIXEL = {
    DimensionTypes.full: appconfig.mediaprocessing.full_still_length,
    DimensionTypes.preview: appconfig.mediaprocessing.preview_still_length,
    DimensionTypes.thumbnail: appconfig.mediaprocessing.thumbnail_still_length,
}


class Database:
    def __init__(self): ...

    def add_item(self, item: Mediaitem):
        # add to db and notify
        with Session(engine) as session:
            session.add(item)
            session.commit()
            session.refresh(item)

    def update_item(self, item: Mediaitem):
        with Session(engine) as session:
            session.add(item)
            session.commit()
            session.refresh(item)

    def delete_item(self, item: Mediaitem):
        with Session(engine) as session:
            session.delete(item)
            session.commit()

    def clear_all(self) -> int:
        with Session(engine) as session:
            statement = delete(Mediaitem)
            result = cast(CursorResult, session.execute(statement))
            session.commit()

            return result.rowcount

    def count(self) -> int:
        with Session(engine) as session:
            statement = select(func.count(Mediaitem.id))
            return session.scalars(statement).one()

    def list_items(self, offset: int = 0, limit: int = 500) -> list[Mediaitem]:
        with Session(engine) as session:
            galleryitems = list(
                session.scalars(
                    select(Mediaitem).where(Mediaitem.show_in_gallery).order_by(Mediaitem.created_at.desc()).offset(offset).limit(limit)
                ).all()
            )

            return galleryitems

    def get_item(self, item_id: UUID) -> Mediaitem:
        try:
            with Session(engine) as session:
                results = session.scalars(select(Mediaitem).where(Mediaitem.id == item_id))
                item = results.one()

                return item
        except NoResultFound as exc:
            raise FileNotFoundError(f"could not find {item_id} in database") from exc


class Files:
    def __init__(self): ...

    def check_representing_files_raise(self, item: Mediaitem):
        if not item.unprocessed.is_file():
            raise FileNotFoundError(f"failed to process {item.id} because representing unprocessed file does not exist: {item.unprocessed}")
        if not item.processed.is_file():
            raise FileNotFoundError(f"failed to process {item.id} because representing processed file does not exist: {item.processed}")

    def delete_item(self, mediaitem: Mediaitem, delete_to_recycle_dir: bool = True):
        """delete single items processed and unprocessed"""

        logger.info(f"request delete files of {mediaitem}")

        if mediaitem.captured_original:
            if delete_to_recycle_dir:
                logger.info(f"moving {mediaitem} to recycle directory")
                mediaitem.captured_original.rename(Path(RECYCLE_PATH, mediaitem.unprocessed.name))
            else:
                mediaitem.captured_original.unlink(missing_ok=True)

        for file in [mediaitem.processed, mediaitem.unprocessed]:  # could be extended to other processed versions if any again...
            file.unlink(missing_ok=True)

        logger.info(f"deleted files of {mediaitem}")

    def clear_all(self):
        """delete all images, inclusive thumbnails, ..."""
        try:
            for file in Path(f"{PATH_UNPROCESSED}").glob("*.*"):
                file.unlink()
            for file in Path(f"{PATH_PROCESSED}").glob("*.*"):
                file.unlink()
            for file in Path(f"{PATH_CAMERA_ORIGINAL}").glob("*.*"):
                file.unlink()
            for item in Path(f"{TMP_PATH}").glob("*"):
                if item.is_file() or item.is_symlink():
                    item.unlink()
                elif item.is_dir():
                    shutil.rmtree(item)

        except Exception as exc:
            logger.exception(exc)
            raise exc

        logger.info("deleted all files for mediaitems")


class Cache:
    def __init__(self):
        self._lock_cache_check: Lock = Lock()

    def get_cached_repr(self, item: Mediaitem, dimension: DimensionTypes, processed: bool = True) -> Cacheditem:
        dimension_pixel = MAP_DIMENSION_TO_PIXEL.get(dimension, None)

        if not item.id:
            raise ValueError("there is no item.id given - cannot create cached representation without id!")
        if dimension_pixel is None:
            raise ValueError(f"invalid dimension given: '{dimension}'")

        with Session(engine) as session:
            # if there are multiple requests for same item at the same time,
            # it might lead to generate cached versions multiple times wasting cpu until it's done.
            # so it's locked from the moment it's checked but that means there is only one process
            # at a time. Maybe a queue is more efficient, but it's ok for now probably.
            with self._lock_cache_check:
                cacheditem_exists = self._db_check_cache_valid(item.id, dimension, processed)

                if cacheditem_exists:
                    return cacheditem_exists

                else:
                    id = uuid4()
                    cacheditem_new = Cacheditem(
                        id=id,
                        mediaitem_id=item.id,
                        dimension=dimension,
                        processed=processed,
                        filepath=Path(CACHE_PATH, id.hex).with_suffix(item.unprocessed.suffix),
                    )

                    with MetricsTimer(f"generate resized '{dimension.value}' for {cacheditem_new.filepath}"):
                        resize(
                            filepath_in=item.processed if processed else item.unprocessed,
                            filepath_out=cacheditem_new.filepath,
                            scaled_min_length=dimension_pixel,
                        )

                    session.add(cacheditem_new)
                    session.commit()
                    session.refresh(cacheditem_new)  # refresh so consuming function can access the attributes in cacheditem_new without session

                    return cacheditem_new

    def _db_check_cache_valid(self, mediaitem_id: UUID, dimension: DimensionTypes, processed: bool = True):
        with Session(engine) as session:
            results = session.scalars(
                select(Cacheditem)
                .join(Mediaitem)
                .where(Cacheditem.mediaitem_id == mediaitem_id, Cacheditem.dimension == dimension, Cacheditem.processed == processed)
                .where(Mediaitem.updated_at < Cacheditem.created_at)  # cached item created later than last updated mediaitem
            )

            cacheditem_exists = results.one_or_none()  # if none, there is no item yet cached and cached version needs to be created.

            # check files also, otherwise delete the item:
            if cacheditem_exists and not cacheditem_exists.filepath.exists():
                logger.warning("deleting cached item from DB because file representation does not exist any more.")
                session.delete(cacheditem_exists)
                session.commit()

                return None

            return cacheditem_exists

    def on_start_maintain(self):
        outdated_filepaths: list[Path] = []

        with Session(engine) as session:
            statement = select(Cacheditem).join(Mediaitem).where(Mediaitem.updated_at > Cacheditem.created_at)
            results = session.scalars(statement)
            outdated_items = results.all()

            for outdated_item in outdated_items:
                outdated_filepaths.append(outdated_item.filepath)
                session.delete(outdated_item)

            session.commit()

            logger.info(f"deleted {len(outdated_items)} outdated items from the cache")

            for outdated_filepath in outdated_filepaths:
                try:
                    outdated_filepath.unlink()
                except Exception as exc:
                    logger.warning(f"could not delete file {outdated_filepath} from cache, error: {exc}")

    def clear_all(self):
        self.db_clear_all()
        self.fs_clear_all()

    def db_clear_all(self):
        with Session(engine) as session:
            statement = delete(Cacheditem)
            session.execute(statement)
            session.commit()

    def fs_clear_all(self):
        for file in Path(f"{CACHE_PATH}").glob("*.*"):
            file.unlink()

        logger.info("deleted all files for mediaitems")


class MediacollectionService(BaseService):
    """Handle all image related stuff"""

    def __init__(self):
        super().__init__()

        self.cache: Cache = Cache()
        self.db: Database = Database()
        self.fs: Files = Files()

        # don't access database during init because it might not be set up during tests...

    def start(self):
        super().start()

        self.on_start_maintain()

        logger.info(f"initialized DB, found {self.count()} images")

        super().started()

    def stop(self):
        super().stop()

        super().stopped()

    def on_start_maintain(self):
        # remove outdated items from cache during startup.
        self.cache.on_start_maintain()

    def add_item(self, item: Mediaitem):
        # check files are avail:
        self.fs.check_representing_files_raise(item)

        self.db.add_item(item)

        pluggy_pm.hook.collection_files_added(files=[item.processed, item.unprocessed])

        if item.captured_original:
            pluggy_pm.hook.collection_original_file_added(files=[item.captured_original])

        # and insert in client db collection so gallery is up to date.
        if item.show_in_gallery:
            sse_service.dispatch_event(SseEventDbInsert(mediaitem=MediaitemPublic.model_validate(item)))

        return item.id

    def update_item(self, item: Mediaitem):
        self.fs.check_representing_files_raise(item)

        self.db.update_item(item)

        pluggy_pm.hook.collection_files_updated(files=[item.processed])

        # send update not to clients, so they can load updated images in case needed.
        sse_service.dispatch_event(SseEventDbUpdate(mediaitem=MediaitemPublic.model_validate(item)))

    def delete_item(self, item: Mediaitem):
        self.db.delete_item(item)
        self.fs.delete_item(item, appconfig.common.users_delete_to_recycle_dir)

        pluggy_pm.hook.collection_files_deleted(files=[item.processed, item.unprocessed])

        # # and remove from client db collection so gallery is up to date.
        # event is even sent if not show_in_gallery, client needs to sort things out
        sse_service.dispatch_event(SseEventDbRemove(mediaitem=MediaitemPublic.model_validate(item)))

    def clear_all(self):
        deleted_count = self.db.clear_all()
        logger.info(f"deleted {deleted_count} items from the database")

        self.fs.clear_all()
        logger.info("media files cleared")

        self.cache.clear_all()
        logger.info("cache cleared")

    def count(self) -> int:
        return self.db.count()

    def list_items(self, offset: int = 0, limit: int = 500) -> list[Mediaitem]:
        return self.db.list_items(offset, limit)

    def get_item(self, item_id: UUID, check_representing_files_raise: bool = True) -> Mediaitem:
        assert isinstance(item_id, UUID), "item_id must be UUID type!"

        item = self.db.get_item(item_id)

        if check_representing_files_raise:
            # on delete the check is usually skipped, because we want to proceed deleting then and need item returned...
            self.fs.check_representing_files_raise(item)

        return item

    def get_item_latest(self) -> Mediaitem:
        try:
            with Session(engine) as session:
                return session.scalars(select(Mediaitem).order_by(Mediaitem.rowid.desc()).limit(1)).one()
        except NoResultFound as exc:
            raise FileNotFoundError("could not find an item") from exc

    def get_items_relto_job(self, job_identifier: UUID) -> list[Mediaitem]:
        with Session(engine) as session:
            galleryitems = list(
                session.scalars(select(Mediaitem).order_by(Mediaitem.rowid.desc()).where(Mediaitem.job_identifier == job_identifier)).all()
            )

            return galleryitems
