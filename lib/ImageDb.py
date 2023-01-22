
import io
from PIL import Image
import json
import shutil
import hashlib
from turbojpeg import TurboJPEG
from lib.ConfigSettings import settings
from pathlib import Path
import time
import glob
import os
import logging
logger = logging.getLogger(__name__)

DATA_PATH = './data/'
PATH_IMAGE = 'image/'
PATH_PREVIEW = 'preview/'
PATH_THUMBNAIL = 'thumbnail/'


def _dbImageItem(filepath: str, caption: str = ""):

    if (not filepath):
        raise Exception("need filepath")

    filename = os.path.basename(filepath)

    if (caption):
        caption = caption
    else:
        caption = filename

    datetime = os.path.getmtime(f"{DATA_PATH}{PATH_IMAGE}{filename}")

    item = {
        'id': hashlib.md5(filename.encode('utf-8')).hexdigest(),
        'caption': caption,
        'filename': filename,
        'datetime': datetime,
        'image': f"{DATA_PATH}{PATH_IMAGE}{filename}",
        'preview': f"{DATA_PATH}{PATH_PREVIEW}{filename}",
        'thumbnail': f"{DATA_PATH}{PATH_THUMBNAIL}{filename}",
    }

    if not (Path(item['image']).is_file() and Path(item['preview']).is_file() and Path(item['thumbnail']).is_file()):
        raise FileNotFoundError(
            f"the imageset is incomplete, not adding {filename} to database")

    return item


def getScaledJpegByJpeg(buffer_in, quality, scaled_min_width):
    # get original size
    with Image.open(io.BytesIO(buffer_in)) as img:
        width, height = img.size

    scaling_factor = scaled_min_width/width
    # TurboJPEG only allows for decent factors. To keep it simple, config allows freely to adjust the size from 10...100% and find the real factor here:
    # possible scaling factors (TurboJPEG.scaling_factors)   (nominator, denominator)
    # limitation due to turbojpeg lib usage.
    # ({(13, 8), (7, 4), (3, 8), (1, 2), (2, 1), (15, 8), (3, 4), (5, 8), (5, 4), (1, 1),
    # (1, 8), (1, 4), (9, 8), (3, 2), (7, 8), (11, 8)})
    # example: (1,4) will result in 1/4=0.25=25% down scale in relation to the full resolution picture
    allowed_list = [(13, 8), (7, 4), (3, 8), (1, 2), (2, 1), (15, 8), (3, 4),
                    (5, 8), (5, 4), (1, 1), (1, 8), (1, 4), (9, 8), (3, 2), (7, 8), (11, 8)]
    factor_list = [item[0]/item[1] for item in allowed_list]
    scale_factor_turboJPEG = min(enumerate(factor_list),
                                 key=lambda x: abs(x[1]-scaling_factor))
    logger.debug(
        f"determined scale factor: {scale_factor_turboJPEG[1]}, index {scale_factor_turboJPEG[0]}, tuple {allowed_list[scale_factor_turboJPEG[0]]}, in width {width}, target width {scaled_min_width}")

    jpeg = TurboJPEG()
    buffer_out = (jpeg.scale_with_quality(
        buffer_in, scaling_factor=allowed_list[scale_factor_turboJPEG[0]], quality=quality))
    return buffer_out


def writeJpegToFile(buffer, filepath):
    with open(filepath, 'wb') as f:
        f.write(buffer)


class ImageDb():
    """Handle all image related stuff"""

    def __init__(self, ee, frameServer, exif):
        self._ee = ee
        self._frameServer = frameServer
        self._exif = exif

        self._db = []  # sorted array. always newest image first in list.

        # TODO: check all directory exist and are writeable - otherwise raise exception.

        self._ee.on("statemachine/capture", self.captureHqImage)

        self._init_db()

    def _init_db(self):
        logger.info(
            "init database and creating missing scaled images. this might take some time.")
        image_paths = sorted(glob.glob(f"{DATA_PATH}{PATH_IMAGE}*.jpg"))
        counterFailedImages = 0

        for image_path in image_paths:

            try:
                id = self._dbAddItem(_dbImageItem(image_path))

            except FileNotFoundError:
                # _dbImageItem raises FileNotFoundError if image/preview/thumb is missing.
                logger.debug(
                    f"file {image_path} misses its scaled versions, try to create now")

                # try create missing preview/thumbnail and retry. otherwise fail completely
                try:
                    with open(image_path, 'rb') as f:
                        self.createScaledImages(f.read(), image_path)
                except Exception as e:
                    logger.error(
                        f"file {image_path} is not readable or scaled images not created. file ignored. {e}")
                    counterFailedImages += 1
                else:
                    id = self._dbAddItem(_dbImageItem(image_path))

        logger.info(
            f"initialized image DB, added {self.numberOfImages} valid images")
        if counterFailedImages:
            logger.error(
                f"{counterFailedImages} some files have errors, go and check the data dir for problems")

    def _dbAddItem(self, item):
        self._db.insert(0, item)  # insert at first position (prepend)
        return item['id']

    def _dbDeleteItemByItem(self, item):
        # self._db = [item for item in self._db if item['id'] != id]
        self._db.remove(item)
        # del self._db[id]

    def _dbDeleteItems(self):
        self._db.clear()

    @property
    def numberOfImages(self):
        return len(self._db)

    def dbGetImages(self, sortByKey="datetime", reverse=True):
        return sorted(self._db, key=lambda x: x[sortByKey], reverse=reverse)
        # return dict(sorted(self._db.items(), key=lambda x: x[1][sortByKey], reverse=reverse))

    def dbGetImageById(self, id):
        # https://stackoverflow.com/a/7125547
        item = next((x for x in self._db if x['id'] == id), None)

        if item == None:
            logger.debug(f"image {id} not found!")
            raise Exception(f"image {id} not found!")

        return item

    """
    processing logic below
    """

    def captureHqImage(self, requested_filepath=None, copyForCompatibility=False):

        start_time = time.time()

        if not requested_filepath:
            requested_filepath = f"{time.strftime('%Y%m%d_%H%M%S')}.jpg"

        logger.debug(f"capture to filename: {requested_filepath}")

        try:

            # at this point it's assumed, a HQ image was requested by statemachine.
            # seems to not make sense now, maybe revert hat...
            self._frameServer.trigger_hq_capture()

            # waitforpic and store to disk
            jpeg_buffer = self._frameServer.wait_for_hq_image()

            # create JPGs and add to db
            (item, id) = self.createImageSetFromImage(
                jpeg_buffer, requested_filepath)
            actual_filepath = item['image']

            # add exif information
            if settings.common.PROCESS_ADD_EXIF_DATA:
                logger.info("add exif data to image")
                try:
                    self._exif.injectExifToJpeg(actual_filepath)
                except Exception as e:
                    logger.exception(
                        f"something went wrong injecting the exif: {e}")

            # also create a copy for photobooth compatibility
            if copyForCompatibility:
                # photobooth sends a complete path, where to put the file, so copy it to requested filepath
                shutil.copy2(actual_filepath, requested_filepath)

            processing_time = round((time.time() - start_time), 1)
            logger.info(
                f"capture to file {actual_filepath} successfull, process took {processing_time}s")

            # to inform frontend about new image to display
            self._ee.emit("publishSSE", sse_event="imagedb/newarrival",
                          sse_data=json.dumps(item))

            return (f'Done, frame capture successful')
        except Exception as e:
            logger.exception(e)

    def createScaledImages(self, buffer_full, filepath):
        filename = os.path.basename(filepath)

        logger.debug(
            f"filesize full image: {round(len(buffer_full)/1024,1)}")

        # preview version
        prev_filepath = f"{DATA_PATH}{PATH_PREVIEW}{filename}"
        buffer_preview = getScaledJpegByJpeg(
            buffer_full, settings.common.PREVIEW_QUALITY, settings.common.PREVIEW_MIN_WIDTH)
        writeJpegToFile(
            buffer_preview, prev_filepath)
        logger.debug(
            f"filesize preview: {round(len(buffer_preview)/1024,1)}")
        logger.info(f"created and saved preview image {prev_filepath}")

        # thumbnail version
        thumb_filepath = f"{DATA_PATH}{PATH_THUMBNAIL}{filename}"
        buffer_thumbnail = getScaledJpegByJpeg(
            buffer_full, settings.common.THUMBNAIL_QUALITY, settings.common.THUMBNAIL_MIN_WIDTH)
        writeJpegToFile(
            buffer_thumbnail, thumb_filepath)
        logger.debug(
            f"filesize thumbnail: {round(len(buffer_thumbnail)/1024,1)}")
        logger.info(f"created and saved thumbnail image {thumb_filepath}")

    def createImageSetFromImage(self, hires_image, filepath):
        """
        A newly captured frame was taken by camera, now its up to this class to create the thumbnail, preview
        finally event is sent when processing is finished
        """
        if not filepath:
            filepath = f"{time.strftime('%Y%m%d_%H%M%S')}.jpg"
        filename = os.path.basename(filepath)

        # create JPGs
        buffer_full = hires_image

        # save to disk
        writeJpegToFile(
            buffer_full, f"{DATA_PATH}{PATH_IMAGE}{filename}")

        # create scaled versions of full image
        self.createScaledImages(buffer_full, filename)

        item = _dbImageItem(filename)
        id = self._dbAddItem(item)

        return item, id

    def deleteImageById(self, id):
        """ delete single file and it's related thumbnails """
        logger.info(f"request delete item id {id}")

        try:
            item = self.dbGetImageById(id)
            logger.debug(f"found item={item}")

            os.remove(item['image'])
            os.remove(item['preview'])
            os.remove(item['thumbnail'])
            self._dbDeleteItemByItem(item)
        except Exception as e:
            logger.exception(f"error deleting item id={id}, error {e}")
            raise

    def deleteImages(self):
        """ delete all images, inclusive thumbnails, ..."""
        try:
            for file in os.scandir(f"{DATA_PATH}{PATH_IMAGE}*.jpg"):
                os.remove(file.path)
            for file in os.scandir(f"{DATA_PATH}{PATH_PREVIEW}*.jpg"):
                os.remove(file.path)
            for file in os.scandir(f"{DATA_PATH}{PATH_THUMBNAIL}*.jpg"):
                os.remove(file.path)
            self._dbDeleteItems()
        except OSError as e:
            raise Exception(
                f"error deleting file {file.path} {e}")
