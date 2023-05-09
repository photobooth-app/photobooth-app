"""
Handle all media collection related functions
"""
import glob
import hashlib
import io
import logging
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import List

from PIL import Image
from turbojpeg import TurboJPEG

from ..appconfig import AppConfig
from .baseservice import BaseService

turbojpeg = TurboJPEG()
settings = AppConfig()
logger = logging.getLogger(__name__)

DATA_PATH = "./data/"
PATH_ORIGINAL = "".join([DATA_PATH, "original/"])
PATH_FULL = "".join([DATA_PATH, "full/"])
PATH_PREVIEW = "".join([DATA_PATH, "preview/"])
PATH_THUMBNAIL = "".join([DATA_PATH, "thumbnail/"])


@dataclass
class MediaItem:
    """Class for keeping track of an media item in dict database."""

    filename: str = None

    @property
    def id(self) -> str:
        return hashlib.md5(self.filename.encode("utf-8")).hexdigest()

    @property
    def caption(self) -> str:
        return Path(self.filename).stem

    @property
    def datetime(self) -> float:
        # cache useful here?
        return os.path.getmtime(self.path_full)

    @property
    def ext_download_url(self) -> str:
        return settings.common.EXT_DOWNLOAD_URL.format(filename=self.filename)

    @property
    def path_original(self) -> Path:
        """filepath of item straight from device/webcam/DSLR, totally unprocessed
        internal use in imagedb"""
        return Path(PATH_ORIGINAL, self.filename)

    @property
    def path_full(self) -> Path:
        """filepath of media item full resolution from device but processed, example background/beautyfilter
        internal use in imagedb"""
        return Path(PATH_FULL, self.filename)

    @property
    def path_preview(self) -> Path:
        """filepath of media item preview resolution scaled represents full
        internal use in imagedb"""
        return Path(PATH_PREVIEW, self.filename)

    @property
    def path_thumbnail(self) -> Path:
        """filepath of media item thumbnail resolution scaled represents full
        internal use in imagedb"""
        return Path(PATH_THUMBNAIL, self.filename)

    @property
    def original(self) -> str:
        """filepath of item straight from device/webcam/DSLR, totally unprocessed
        external use as urls"""
        return Path(PATH_ORIGINAL, self.filename).as_posix()

    @property
    def full(self) -> str:
        """filepath of media item full resolution from device but processed, example background/beautyfilter
        external use as urls"""
        return Path(PATH_FULL, self.filename).as_posix()

    @property
    def preview(self) -> str:
        """filepath of media item preview resolution scaled represents full
        external use as urls"""
        return Path(PATH_PREVIEW, self.filename).as_posix()

    @property
    def thumbnail(self) -> str:
        """filepath of media item thumbnail resolution scaled represents full
        external use as urls"""
        return Path(PATH_THUMBNAIL, self.filename).as_posix()

    def __post_init__(self):
        if not self.filename:
            raise ValueError("Filename must be given")

        if not (
            (self.path_original).is_file()
            and (self.path_full).is_file()
            and (self.path_preview).is_file()
            and (self.path_thumbnail).is_file()
        ):
            raise FileNotFoundError(
                f"the imageset is incomplete, not adding {self.filename} to database"
            )

    def asdict(self) -> dict:
        """Returns a dict including all properties, excluding __xx__ and other callable functions.
        reference: https://stackoverflow.com/a/51734064

        #TODO: could be improved by reducing the number of properies (for URL and Path) by apply .as_posix here.

        Returns:
            dict: MediaItems
        """
        return {
            prop: getattr(self, prop)
            for prop in dir(self)
            if (
                not prop.startswith("__")  # no privates
                and not callable(getattr(__class__, prop, None))  # no callables
                and not isinstance(
                    getattr(self, prop), Path
                )  # no path instances (not json.serializable)
            )
        }


def get_scaled_jpeg_by_jpeg(buffer_in, quality, scaled_min_width):
    """scale a jpeg buffer to another buffer using turbojpeg"""
    # get original size
    with Image.open(io.BytesIO(buffer_in)) as img:
        width, _ = img.size

    scaling_factor = scaled_min_width / width

    # TurboJPEG only allows for decent factors.
    # To keep it simple, config allows freely to adjust the size from 10...100% and
    # find the real factor here:
    # possible scaling factors (TurboJPEG.scaling_factors)   (nominator, denominator)
    # limitation due to turbojpeg lib usage.
    # ({(13, 8), (7, 4), (3, 8), (1, 2), (2, 1), (15, 8), (3, 4), (5, 8), (5, 4), (1, 1),
    # (1, 8), (1, 4), (9, 8), (3, 2), (7, 8), (11, 8)})
    # example: (1,4) will result in 1/4=0.25=25% down scale in relation to
    # the full resolution picture
    allowed_list = [
        (13, 8),
        (7, 4),
        (3, 8),
        (1, 2),
        (2, 1),
        (15, 8),
        (3, 4),
        (5, 8),
        (5, 4),
        (1, 1),
        (1, 8),
        (1, 4),
        (9, 8),
        (3, 2),
        (7, 8),
        (11, 8),
    ]
    factor_list = [item[0] / item[1] for item in allowed_list]
    scale_factor_turbojpeg = min(
        enumerate(factor_list), key=lambda x: abs(x[1] - scaling_factor)
    )
    logger.info(
        f"determined scale factor: {scale_factor_turbojpeg[1]},"
        f"input img width {width}, target img width {scaled_min_width}"
    )

    buffer_out = turbojpeg.scale_with_quality(
        buffer_in,
        scaling_factor=allowed_list[scale_factor_turbojpeg[0]],
        quality=quality,
    )
    return buffer_out


def create_scaled_files(buffer_full, filepath):
    """_summary_

    Args:
        buffer_full (_type_): _description_
        filepath (_type_): _description_
    """
    filename = os.path.basename(filepath)

    ## full version
    with open(f"{PATH_FULL}{filename}", "wb") as file:
        file.write(buffer_full)

    ## preview version
    buffer_preview = get_scaled_jpeg_by_jpeg(
        buffer_full,
        settings.common.PREVIEW_STILL_QUALITY,
        settings.common.PREVIEW_STILL_WIDTH,
    )
    with open(f"{PATH_PREVIEW}{filename}", "wb") as file:
        file.write(buffer_preview)

    ## thumbnail version
    buffer_thumbnail = get_scaled_jpeg_by_jpeg(
        buffer_full,
        settings.common.THUMBNAIL_STILL_QUALITY,
        settings.common.THUMBNAIL_STILL_WIDTH,
    )
    with open(f"{PATH_THUMBNAIL}{filename}", "wb") as file:
        file.write(buffer_thumbnail)

    logger.debug(f"filesize full image: {round(len(buffer_full)/1024,1)}kb")
    logger.debug(f"filesize preview: {round(len(buffer_preview)/1024,1)}kb")
    logger.debug(f"filesize thumbnail: {round(len(buffer_thumbnail)/1024,1)}kb")
    logger.info(f"created and saved scaled media items for {filename=}")


def create_imageset_from_originalimage(filename):
    """
    A newly captured frame was taken by camera,
    now its up to this class to create the thumbnail,
    preview finally event is sent when processing is finished
    """

    # read original file

    with open(Path(PATH_ORIGINAL, filename), "rb") as file:
        buffer_original = file.read()
    logger.debug(f"filesize original image: {round(len(buffer_original)/1024,1)}kb")

    ##
    # this could be a place to add a filter pipeline later
    # 1) remove background
    # 2) beauty filter
    # 3) ...

    # create scaled versions of full image
    create_scaled_files(buffer_original, filename)

    item = MediaItem(filename)

    return item


class MediacollectionService(BaseService):
    """Handle all image related stuff"""

    def __init__(self, evtbus):
        super().__init__(evtbus=evtbus)

        # the database ;)
        # sorted list containing type MediaItem. always newest image first in list.
        self._db: List[MediaItem] = []

        # ensure data directories exist
        os.makedirs(f"{PATH_ORIGINAL}", exist_ok=True)
        os.makedirs(f"{PATH_FULL}", exist_ok=True)
        os.makedirs(f"{PATH_PREVIEW}", exist_ok=True)
        os.makedirs(f"{PATH_THUMBNAIL}", exist_ok=True)

        self._init_db()

    def _init_db(self):
        self._logger.info(
            "init database and creating missing scaled images. this might take some time."
        )
        image_paths = sorted(glob.glob(f"{PATH_ORIGINAL}*.jpg"))
        counter_processed_images = 0
        counter_failed_images = 0
        start_time_initialize = time.time()

        for image_path in image_paths:
            filename = Path(image_path).name

            try:
                self.db_add_item(MediaItem(filename))

            except FileNotFoundError:
                # MediaItem raises FileNotFoundError if original/full/preview/thumb is missing.
                self._logger.debug(
                    f"file {filename} misses its scaled versions, try to create now"
                )

                # try create missing preview/thumbnail and retry. otherwise fail completely
                try:
                    create_imageset_from_originalimage(filename)
                    counter_processed_images += 1
                except (FileNotFoundError, PermissionError, OSError) as exc:
                    self._logger.error(
                        f"file {filename} processing failed. file ignored. {exc}"
                    )
                    counter_failed_images += 1
                else:
                    self.db_add_item(MediaItem(filename))

        self._logger.info(
            f"initialized image DB, added {self.number_of_images} valid images"
        )
        self._logger.info(
            f"initialize process time: {round((time.time() - start_time_initialize), 2)}s"
        )
        if counter_processed_images:
            self._logger.warning(
                f"#{counter_processed_images} items processed due to missing scaled version"
            )
        if counter_failed_images:
            self._logger.error(
                f"#{counter_failed_images} erroneous files, check the data dir for problems"
            )

        # finally sort the db one time only. resorting never necessary
        # because new items are inserted at the right place and no sort algorithms are supported currently
        self._db.sort(key=lambda item: item.datetime, reverse=True)

    def db_add_item(self, item: MediaItem):
        self._db.insert(0, item)  # insert at first position (prepend)
        return item.id

    def _db_delete_item_by_item(self, item: MediaItem):
        # self._db = [item for item in self._db if item['id'] != id]
        self._db.remove(item)
        # del self._db[id]

    def _db_delete_items(self):
        self._db.clear()

    @property
    def number_of_images(self) -> int:
        """count number of items in db

        Returns:
            int: Number of items in db
        """
        return len(self._db)

    def db_get_images(self) -> dict:
        """Get dict of mediaitems. Most recent item is at index 0.


        Returns:
            dict: _description_
        """
        return [item.asdict() for item in self._db]

    def db_get_image_by_id(self, item_id):
        """_summary_

        Args:
            item_id (_type_): _description_

        Raises:
            FileNotFoundError: _description_

        Returns:
            _type_: _description_
        """
        # https://stackoverflow.com/a/7125547
        item = next((x for x in self._db if x.id == item_id), None)

        if item is None:
            self._logger.debug(f"image {item_id} not found!")
            raise FileNotFoundError(f"image {item_id} not found!")

        return item

    def delete_image_by_id(self, item_id):
        """delete single file and it's related thumbnails"""
        self._logger.info(f"request delete item id {item_id}")

        try:
            item = self.db_get_image_by_id(item_id)
            self._logger.debug(f"found item={item}")

            os.remove(item.original)
            os.remove(item.full)
            os.remove(item.preview)
            os.remove(item.thumbnail)
            self._db_delete_item_by_item(item)
        except Exception as exc:
            self._logger.exception(exc)
            self._logger.error(f"error deleting item id={item_id}")
            raise exc

    def delete_images(self):
        """delete all images, inclusive thumbnails, ..."""
        try:
            for file in Path(f"{PATH_ORIGINAL}").glob("*.jpg"):
                os.remove(file)
            for file in Path(f"{PATH_FULL}").glob("*.jpg"):
                os.remove(file)
            for file in Path(f"{PATH_PREVIEW}").glob("*.jpg"):
                os.remove(file)
            for file in Path(f"{PATH_THUMBNAIL}").glob("*.jpg"):
                os.remove(file)
            self._db_delete_items()
        except OSError as exc:
            self._logger.exception(exc)
            self._logger.error(f"error deleting file {file}")
