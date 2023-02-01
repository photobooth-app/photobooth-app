from pymitter import EventEmitter
from libcamera import controls
import logging
from ConfigSettings import settings
from ImageServerAbstract import ImageServerAbstract
from lib.ImageServerPicam2AddonAutofocusFocuser import ImageServerPicam2AddonAutofocusFocuser
logger = logging.getLogger(__name__)


class ImageServerPicam2AddonLibcamAutofocus(object):
    def __init__(self, imageServer: ImageServerAbstract, ee: EventEmitter):
        self._imageServer: ImageServerAbstract = imageServer

        self._ee = ee
        self._ee.on("statemachine/armed",
                    self.setIgnoreFocusRequests)
        self._ee.on("statemachine/finished",
                    self.setAllowFocusRequests)
        self._ee.on("onCaptureMode",
                    self.setIgnoreFocusRequests)
        self._ee.on("onPreviewMode",
                    self.setAllowFocusRequests)

        self.setAllowFocusRequests()

    def abortOngoingFocusThread(self):
        self._imageServer._picam2.set_controls(
            {"AfMode": controls.AfModeEnum.Auto})

    def setIgnoreFocusRequests(self):
        self._imageServer._picam2.set_controls(
            {"AfMode": controls.AfModeEnum.Auto})

    def setAllowFocusRequests(self):
        self._imageServer._picam2.set_controls(
            {"AfMode": controls.AfModeEnum.Continuous, "AfSpeed": controls.AfSpeedEnum.Fast})
