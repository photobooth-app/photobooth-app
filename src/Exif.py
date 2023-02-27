"""
create exif data to be injected into jpeg images
"""
import logging
import datetime
import piexif
from src.imageserverabstract import ImageServerAbstract
from src.locationservice import LocationService

logger = logging.getLogger(__name__)


class Exif():
    """Handle all image related stuff"""

    def __init__(self, imageserver: ImageServerAbstract):
        self._imageserver = imageserver
        self._locationservice = LocationService()
        self._locationservice.start()

    def create_exif_bytes(self):
        """create exif bytes using piexif"""
        logger.info(
            f"making up exif data from imageserver metadata={self._imageserver.metadata}")
        # grab metadata from frameserver
        now = datetime.datetime.now()
        zero_ifd = {piexif.ImageIFD.Make: self._imageserver.exif_make,
                    piexif.ImageIFD.Model: self._imageserver.exif_model,
                    piexif.ImageIFD.Software: "Photobooth Imageserver"}
        total_gain = (self._imageserver.metadata.get("AnalogueGain", 0) *
                      self._imageserver.metadata.get("DigitalGain", 0))
        exif_ifd = {piexif.ExifIFD.ExposureTime:
                    (self._imageserver.metadata.get("ExposureTime", 0), 1000000),
                    piexif.ExifIFD.DateTimeOriginal: now.strftime("%Y:%m:%d %H:%M:%S"),
                    piexif.ExifIFD.ISOSpeedRatings: int(total_gain * 100)}

        exif_dict = {"0th": zero_ifd, "Exif": exif_ifd}

        if self._locationservice.accuracy:
            logger.info("adding GPS data to exif")
            logger.debug(
                f"gps location: {self._locationservice.latitude},{self._locationservice.longitude}")

            gps_ifd = {
                piexif.GPSIFD.GPSLatitudeRef: self._locationservice.latitude_ref,
                piexif.GPSIFD.GPSLatitude: self._locationservice.latitude_dms,
                piexif.GPSIFD.GPSLongitudeRef: self._locationservice.longitude_ref,
                piexif.GPSIFD.GPSLongitude: self._locationservice.longitude_dms,
            }
            # add gps dict
            exif_dict.update({"GPS": gps_ifd})
        logger.info(f"gathered following exif data to be injected {exif_dict}")
        exif_bytes = piexif.dump(exif_dict)

        return exif_bytes

    def inject_exif_to_jpeg(self, filepath):
        """implant exif data in jpeg files"""
        # gather data
        exif_bytes = self.create_exif_bytes()
        # insert exif data
        piexif.insert(exif_bytes, filepath)
