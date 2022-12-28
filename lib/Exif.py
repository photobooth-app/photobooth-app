import piexif
import datetime
import logging
from lib.ImageServerAbstract import ImageServerAbstract
from lib.LocationService import LocationService
logger = logging.getLogger(__name__)


class Exif():
    """Handle all image related stuff"""

    def __init__(self, imageServer: ImageServerAbstract, locationservice: LocationService):
        self._imageServer = imageServer
        self._locationservice = locationservice

    def createExifBytes(self):
        print(self._imageServer.metadata)
        # grab metadata from frameserver
        now = datetime.datetime.now()
        zero_ifd = {piexif.ImageIFD.Make: self._imageServer.exif_make,
                    # self._frameServer._picam2.camera.id,
                    piexif.ImageIFD.Model: self._imageServer.exif_model,
                    piexif.ImageIFD.Software: "Photobooth Imageserver"}
        total_gain = (self._imageServer.metadata.get("AnalogueGain", 0) *
                      self._imageServer.metadata.get("DigitalGain", 0))
        exif_ifd = {piexif.ExifIFD.ExposureTime: (self._imageServer.metadata.get("ExposureTime", 0), 1000000),
                    piexif.ExifIFD.DateTimeOriginal: now.strftime("%Y:%m:%d %H:%M:%S"),
                    piexif.ExifIFD.ISOSpeedRatings: int(total_gain * 100)}

        exif_dict = {"0th": zero_ifd, "Exif": exif_ifd}

        if (self._locationservice.accuracy):
            logger.info("adding GPS data to exif")
            logger.debug(
                f"gps location: {self._locationservice.latitude},{self._locationservice.longitude}")

            gps_ifd = {
                piexif.GPSIFD.GPSLatitudeRef: self._locationservice.latitudeRef,
                piexif.GPSIFD.GPSLatitude: self._locationservice.latitudeDMS,
                piexif.GPSIFD.GPSLongitudeRef: self._locationservice.longitudeRef,
                piexif.GPSIFD.GPSLongitude: self._locationservice.longitudeDMS,
            }
            # add gps dict
            exif_dict.update({"GPS": gps_ifd})
        logger.info(f"gathered following exif data to be injected {exif_dict}")
        exif_bytes = piexif.dump(exif_dict)

        return exif_bytes

    def injectExifToJpeg(self, filepath):
        # gater data
        exif_bytes = self.createExifBytes()
        # insert exif data
        piexif.insert(exif_bytes, filepath)
