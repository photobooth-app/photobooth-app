"""
create exif data to be injected into jpeg images
"""
import logging
from PIL import Image
import piexif
from src.locationservice import LocationService

logger = logging.getLogger(__name__)


class Exif:
    """Handle all image related stuff"""

    def __init__(self):
        self._locationservice = LocationService()
        self._locationservice.start()

    def add_geolocation_to_exif_dict(self, exif_dict):
        """create exif bytes using piexif"""

        logger.info("making up exif data")

        if self._locationservice.accuracy:
            logger.info("adding GPS data to exif")
            logger.debug(
                f"gps location: {self._locationservice.latitude},{self._locationservice.longitude}"
            )

            gps_ifd = {
                piexif.GPSIFD.GPSLatitudeRef: self._locationservice.latitude_ref,
                piexif.GPSIFD.GPSLatitude: self._locationservice.latitude_dms,
                piexif.GPSIFD.GPSLongitudeRef: self._locationservice.longitude_ref,
                piexif.GPSIFD.GPSLongitude: self._locationservice.longitude_dms,
            }
            # add gps dict
            exif_dict.update({"GPS": gps_ifd})
        else:
            logger.error("no GPS data avail to add to exif data")

        logger.info(f"gathered following exif data to be injected {exif_dict}")

        return exif_dict

    def inject_exif_to_jpeg(self, filepath):
        """implant exif data in jpeg files"""
        # insert exif data

        img = Image.open(filepath)
        try:
            exif_dict = piexif.load(img.info["exif"])
        except KeyError:
            # img has no exif data, create empty dict here so following process can update dict
            exif_dict = {}

        piexif.insert(
            piexif.dump(self.add_geolocation_to_exif_dict(exif_dict=exif_dict)),
            filepath,
        )
