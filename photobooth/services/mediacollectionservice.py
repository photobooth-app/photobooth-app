"""
Handle all media collection related functions
"""
import logging
import os
import time
from pathlib import Path

from .baseservice import BaseService
from .mediacollection.mediaitem import (
    PATH_FULL,
    PATH_FULL_UNPROCESSED,
    PATH_ORIGINAL,
    PATH_PREVIEW,
    PATH_PREVIEW_UNPROCESSED,
    PATH_THUMBNAIL,
    PATH_THUMBNAIL_UNPROCESSED,
    MediaItem,
    MediaItemAllowedFileendings,
)
from .mediaprocessingservice import MediaprocessingService
from .sseservice import SseEventDbInsert, SseEventDbRemove, SseService

logger = logging.getLogger(__name__)


class MediacollectionService(BaseService):
    """Handle all image related stuff"""

    def __init__(
        self,
        sse_service: SseService,
        mediaprocessing_service: MediaprocessingService,
    ):
        super().__init__(sse_service=sse_service)

        self._mediaprocessing_service: MediaprocessingService = mediaprocessing_service

        # the database ;)
        # sorted list containing type MediaItem. always newest image first in list.
        self._db: list[MediaItem] = []

        # ensure data directories exist
        os.makedirs(f"{PATH_ORIGINAL}", exist_ok=True)
        os.makedirs(f"{PATH_FULL}", exist_ok=True)
        os.makedirs(f"{PATH_PREVIEW}", exist_ok=True)
        os.makedirs(f"{PATH_THUMBNAIL}", exist_ok=True)
        os.makedirs(f"{PATH_FULL_UNPROCESSED}", exist_ok=True)
        os.makedirs(f"{PATH_PREVIEW_UNPROCESSED}", exist_ok=True)
        os.makedirs(f"{PATH_THUMBNAIL_UNPROCESSED}", exist_ok=True)

        self._init_db()

    def _init_db(self):
        self._logger.info("init database and creating missing scaled images. this might take some time.")

        search_for_fileendings = [f".{e.value}" for e in MediaItemAllowedFileendings]
        self._logger.info(f"watching for filetypes: {search_for_fileendings}")
        image_paths = (p.resolve() for p in Path(PATH_ORIGINAL).glob("**/*") if p.suffix in search_for_fileendings)

        start_time_initialize = time.time()

        for image_path in image_paths:
            filename = Path(image_path).name

            try:
                mediaitem = MediaItem(filename)
                mediaitem.ensure_scaled_repr_created()
                self.db_add_item(mediaitem)

            except Exception as exc:
                self._logger.error(f"file {filename} processing failed. file ignored. {exc}")

        self._logger.info(f"initialized image DB, added {self.number_of_images} valid images")
        self._logger.info(f"-- process time: {round((time.time() - start_time_initialize), 2)}s to initialize mediacollection")

        # finally sort the db one time only. resorting never necessary
        # because new items are inserted at the right place and no sort algorithms are supported currently
        self._db.sort(key=lambda item: item.datetime, reverse=True)

    def db_add_item(self, item: MediaItem):
        self._db.insert(0, item)  # insert at first position (prepend)

        # and insert in client db collection so gallery is up to date.
        self._sse_service.dispatch_event(SseEventDbInsert(mediaitem=item))

        return item.id

    def _db_delete_item_by_item(self, item: MediaItem):
        self._db.remove(item)

        # and remove from client db collection so gallery is up to date.
        self._sse_service.dispatch_event(SseEventDbRemove(mediaitem=item))

    def _db_delete_items(self):
        self._db.clear()

    @property
    def number_of_images(self) -> int:
        """count number of items in db

        Returns:
            int: Number of items in db
        """
        return len(self._db)

    def db_get_images_as_dict(self) -> list:
        """Get dict of mediaitems. Most recent item is at index 0.


        Returns:
            list: _description_
        """
        tms = time.time()
        out = [item.asdict() for item in self._db if item.visible]
        logger.debug(f"-- process time: {round((time.time() - tms), 2)}s to compile db_get_images_as_dict output")
        return out

    def db_get_images(self) -> list[MediaItem]:
        """Get list of mediaitems. Most recent item is at index 0.


        Returns:
            list: _description_
        """
        return [item for item in self._db if item.visible]

    def db_get_most_recent_mediaitem(self):
        # get most recent item
        # most recent item is in 0 index.

        if not self._db:
            # empty database
            raise FileNotFoundError("database is empty")

        return self._db[0]

    def db_get_image_by_id(self, item_id: str):
        """_summary_

        Args:
            item_id (_type_): _description_

        Raises:
            FileNotFoundError: _description_

        Returns:
            _type_: _description_
        """
        if not isinstance(item_id, str):
            raise RuntimeError("item_id is wrong type")

        # https://stackoverflow.com/a/7125547
        item = next((x for x in self._db if x.id == item_id), None)

        if item is None:
            self._logger.debug(f"image {item_id} not found!")
            raise FileNotFoundError(f"image {item_id} not found!")

        return item

    def delete_image_by_id(self, item_id: str):
        """delete single file and it's related thumbnails"""
        if not isinstance(item_id, str):
            raise RuntimeError("item_id is wrong type")

        self._logger.info(f"request delete item id {item_id}")

        try:
            # lookup item in collection
            item = self.db_get_image_by_id(item_id)
            self._logger.debug(f"found item={item}")

            # remove files from disk
            self.delete_mediaitem_files(item)

            # remove from collection
            self._db_delete_item_by_item(item)
        except Exception as exc:
            self._logger.exception(exc)
            self._logger.error(f"error deleting item id={item_id}")

        self._logger.debug(f"deleted mediaitem from db and files {item}")

    def delete_mediaitem_files(self, mediaitem: MediaItem):
        """delete single file and it's related thumbnails"""

        self._logger.info(f"request delete files of {mediaitem}")

        try:
            os.remove(mediaitem.path_original)
            os.remove(mediaitem.path_full_unprocessed)
            os.remove(mediaitem.path_full)
            os.remove(mediaitem.path_preview_unprocessed)
            os.remove(mediaitem.path_preview)
            os.remove(mediaitem.path_thumbnail_unprocessed)
            os.remove(mediaitem.path_thumbnail)
        except Exception as exc:
            self._logger.exception(exc)
            self._logger.error(f"error deleting files for item {mediaitem}")

        self._logger.info(f"deleted files of {mediaitem}")

    def delete_images(self):
        """delete all images, inclusive thumbnails, ..."""
        try:
            for file in Path(f"{PATH_ORIGINAL}").glob("*.*"):
                os.remove(file)
            for file in Path(f"{PATH_FULL}").glob("*.*"):
                os.remove(file)
            for file in Path(f"{PATH_PREVIEW}").glob("*.*"):
                os.remove(file)
            for file in Path(f"{PATH_THUMBNAIL}").glob("*.*"):
                os.remove(file)
            for file in Path(f"{PATH_FULL_UNPROCESSED}").glob("*.*"):
                os.remove(file)
            for file in Path(f"{PATH_PREVIEW_UNPROCESSED}").glob("*.*"):
                os.remove(file)
            for file in Path(f"{PATH_THUMBNAIL_UNPROCESSED}").glob("*.*"):
                os.remove(file)
            self._db_delete_items()
        except OSError as exc:
            self._logger.exception(exc)
            self._logger.error(f"error deleting file {file}")
