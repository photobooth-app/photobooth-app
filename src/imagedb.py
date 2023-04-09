"""
Handle all media collection related functions
"""
import io
import json
import time
import glob
import os
import logging
import shutil
import hashlib
from pathlib import Path
from PIL import Image
from turbojpeg import TurboJPEG
from src.configsettings import settings
from src.exif import Exif

logger = logging.getLogger(__name__)

DATA_PATH = "./data/"
PATH_IMAGE = "image/"
PATH_PREVIEW = "preview/"
PATH_THUMBNAIL = "thumbnail/"


def _db_imageitem(filepath: str, user_caption: str = ""):
    if not filepath:
        raise ValueError("need filepath")

    filename = os.path.basename(filepath)

    caption = filename
    if user_caption:
        # overwrite caption if provided
        caption = user_caption

    datetime = os.path.getmtime(f"{DATA_PATH}{PATH_IMAGE}{filename}")

    item = {
        "id": hashlib.md5(filename.encode("utf-8")).hexdigest(),
        "caption": caption,
        "filename": filename,
        "datetime": datetime,
        "image": f"{DATA_PATH}{PATH_IMAGE}{filename}",
        "preview": f"{DATA_PATH}{PATH_PREVIEW}{filename}",
        "thumbnail": f"{DATA_PATH}{PATH_THUMBNAIL}{filename}",
        "ext_download_url": settings.common.EXT_DOWNLOAD_URL.format(filename=filename),
    }

    if not (
        Path(item["image"]).is_file()
        and Path(item["preview"]).is_file()
        and Path(item["thumbnail"]).is_file()
    ):
        raise FileNotFoundError(
            f"the imageset is incomplete, not adding {filename} to database"
        )

    return item


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
    logger.debug(
        f"determined scale factor: {scale_factor_turbojpeg[1]},"
        f"index {scale_factor_turbojpeg[0]}, tuple {allowed_list[scale_factor_turbojpeg[0]]},"
        f"in width {width}, target width {scaled_min_width}"
    )

    jpeg = TurboJPEG()
    buffer_out = jpeg.scale_with_quality(
        buffer_in,
        scaling_factor=allowed_list[scale_factor_turbojpeg[0]],
        quality=quality,
    )
    return buffer_out


def write_jpeg_to_file(buffer, filepath):
    """store buffer to given filepath"""
    with open(filepath, "wb") as file:
        file.write(buffer)


class ImageDb:
    """Handle all image related stuff"""

    def __init__(self, evtbus, imageserver):
        self._evtbus = evtbus
        self._imageserver = imageserver
        self._exif = Exif(self._imageserver)

        self._db = []  # sorted array. always newest image first in list.

        self._evtbus.on("statemachine/capture", self.capture_hq_image)

        self._init_db()

    def _init_db(self):
        logger.info(
            "init database and creating missing scaled images. this might take some time."
        )
        image_paths = sorted(glob.glob(f"{DATA_PATH}{PATH_IMAGE}*.jpg"))
        counter_failed_images = 0

        for image_path in image_paths:
            try:
                self._db_add_item(_db_imageitem(image_path))

            except FileNotFoundError:
                # _dbImageItem raises FileNotFoundError if image/preview/thumb is missing.
                logger.debug(
                    f"file {image_path} misses its scaled versions, try to create now"
                )

                # try create missing preview/thumbnail and retry. otherwise fail completely
                try:
                    with open(image_path, "rb") as file:
                        self.create_scaled_images(file.read(), image_path)
                except (FileNotFoundError, PermissionError, OSError) as exc:
                    logger.error(
                        f"file {image_path} processing failed. file ignored. {exc}"
                    )
                    counter_failed_images += 1
                else:
                    self._db_add_item(_db_imageitem(image_path))

        logger.info(f"initialized image DB, added {self.number_of_images} valid images")
        if counter_failed_images:
            logger.error(
                f"#{counter_failed_images} erroneous files, check the data dir for problems"
            )

    def _db_add_item(self, item):
        self._db.insert(0, item)  # insert at first position (prepend)
        return item["id"]

    def _db_delete_item_by_item(self, item):
        # self._db = [item for item in self._db if item['id'] != id]
        self._db.remove(item)
        # del self._db[id]

    def _db_delete_items(self):
        self._db.clear()

    @property
    def number_of_images(self):
        """_summary_

        Returns:
            _type_: _description_
        """
        return len(self._db)

    def db_get_images(self, sort_by_key="datetime", reverse=True):
        """_summary_

        Args:
            sort_by_key (str, optional): _description_. Defaults to "datetime".
            reverse (bool, optional): _description_. Defaults to True.

        Returns:
            _type_: _description_
        """
        return sorted(self._db, key=lambda x: x[sort_by_key], reverse=reverse)
        # return dict(sorted(self._db.items(), key=lambda x: x[1][sortByKey], reverse=reverse))

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
        item = next((x for x in self._db if x["id"] == item_id), None)

        if item is None:
            logger.debug(f"image {item_id} not found!")
            raise FileNotFoundError(f"image {item_id} not found!")

        return item

    def capture_hq_image(self, requested_filepath=None, copy_for_compatibility=False):
        """
        trigger still image capture and align post processing
        """
        start_time = time.time()

        if not requested_filepath:
            requested_filepath = f"{time.strftime('%Y%m%d_%H%M%S')}.jpg"

        logger.debug(f"capture to filename: {requested_filepath}")

        # at this point it's assumed, a HQ image was requested by statemachine.
        # seems to not make sense now, maybe revert hat...
        # waitforpic and store to disk
        jpeg_buffer = self._imageserver.wait_for_hq_image()

        # create JPGs and add to db
        (item, _) = self.create_imageset_from_image(jpeg_buffer, requested_filepath)
        actual_filepath = item["image"]

        # add exif information
        if settings.common.PROCESS_ADD_EXIF_DATA:
            logger.info("add exif data to image")
            self._exif.inject_exif_to_jpeg(actual_filepath)

        # also create a copy for photobooth compatibility
        if copy_for_compatibility:
            # photobooth sends a complete path, where to put the file,
            # so copy it to requested filepath
            shutil.copy2(actual_filepath, requested_filepath)

        processing_time = round((time.time() - start_time), 1)
        logger.info(
            f"capture to file {actual_filepath} successfull, process took {processing_time}s"
        )

        # to inform frontend about new image to display
        self._evtbus.emit(
            "publishSSE", sse_event="imagedb/newarrival", sse_data=json.dumps(item)
        )

    def create_scaled_images(self, buffer_full, filepath):
        """_summary_

        Args:
            buffer_full (_type_): _description_
            filepath (_type_): _description_
        """
        filename = os.path.basename(filepath)

        logger.debug(f"filesize full image: {round(len(buffer_full)/1024,1)}")

        # preview version
        prev_filepath = f"{DATA_PATH}{PATH_PREVIEW}{filename}"
        buffer_preview = get_scaled_jpeg_by_jpeg(
            buffer_full,
            settings.common.PREVIEW_STILL_QUALITY,
            settings.common.PREVIEW_STILL_WIDTH,
        )
        write_jpeg_to_file(buffer_preview, prev_filepath)
        logger.debug(f"filesize preview: {round(len(buffer_preview)/1024,1)}")
        logger.info(f"created and saved preview image {prev_filepath}")

        # thumbnail version
        thumb_filepath = f"{DATA_PATH}{PATH_THUMBNAIL}{filename}"
        buffer_thumbnail = get_scaled_jpeg_by_jpeg(
            buffer_full,
            settings.common.THUMBNAIL_STILL_QUALITY,
            settings.common.THUMBNAIL_STILL_WIDTH,
        )
        write_jpeg_to_file(buffer_thumbnail, thumb_filepath)
        logger.debug(f"filesize thumbnail: {round(len(buffer_thumbnail)/1024,1)}")
        logger.info(f"created and saved thumbnail image {thumb_filepath}")

    def create_imageset_from_image(self, hires_image, filepath):
        """
        A newly captured frame was taken by camera,
        now its up to this class to create the thumbnail,
        preview finally event is sent when processing is finished
        """
        if not filepath:
            filepath = f"{time.strftime('%Y%m%d_%H%M%S')}.jpg"
        filename = os.path.basename(filepath)

        # create JPGs
        buffer_full = hires_image

        # save to disk
        write_jpeg_to_file(buffer_full, f"{DATA_PATH}{PATH_IMAGE}{filename}")

        # create scaled versions of full image
        self.create_scaled_images(buffer_full, filename)

        item = _db_imageitem(filename)
        item_id = self._db_add_item(item)

        return item, item_id

    def delete_image_by_id(self, item_id):
        """delete single file and it's related thumbnails"""
        logger.info(f"request delete item id {item_id}")

        try:
            item = self.db_get_image_by_id(item_id)
            logger.debug(f"found item={item}")

            os.remove(item["image"])
            os.remove(item["preview"])
            os.remove(item["thumbnail"])
            self._db_delete_item_by_item(item)
        except Exception as exc:
            logger.exception(exc)
            logger.error(f"error deleting item id={item_id}")
            raise

    def delete_images(self):
        """delete all images, inclusive thumbnails, ..."""
        try:
            for file in Path(f"{DATA_PATH}{PATH_IMAGE}").glob("*.jpg"):
                os.remove(file)
            for file in Path(f"{DATA_PATH}{PATH_PREVIEW}").glob("*.jpg"):
                os.remove(file)
            for file in Path(f"{DATA_PATH}{PATH_THUMBNAIL}").glob("*.jpg"):
                os.remove(file)
            self._db_delete_items()
        except OSError as exc:
            logger.exception(exc)
            logger.error(f"error deleting file {file}")
