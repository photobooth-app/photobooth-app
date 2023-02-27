"""
autofocus control using native libcamera functions
"""
import logging
from libcamera import controls
from pymitter import EventEmitter
from src.imageserverabstract import ImageServerAbstract

logger = logging.getLogger(__name__)


class ImageServerPicam2AddonLibcamAutofocus():
    """
    native libcamera control autofocus implementation
    """

    def __init__(self, imageserver: ImageServerAbstract, evtbus: EventEmitter):
        self._imageserver: ImageServerAbstract = imageserver

        self._evtbus = evtbus
        self._evtbus.on("statemachine/armed",
                        self.set_ignore_focus_requests)
        self._evtbus.on("statemachine/finished",
                        self.set_allow_focus_requests)
        self._evtbus.on("onCaptureMode",
                        self.set_ignore_focus_requests)
        self._evtbus.on("onPreviewMode",
                        self.set_allow_focus_requests)

        self.set_allow_focus_requests()

    def abort_ongoing_focus_thread(self):
        self._imageserver._picam2.set_controls(
            {"AfMode": controls.AfModeEnum.Auto})

    def set_ignore_focus_requests(self):
        self._imageserver._picam2.set_controls(
            {"AfMode": controls.AfModeEnum.Auto})

    def set_allow_focus_requests(self):
        self._imageserver._picam2.set_controls(
            {"AfMode": controls.AfModeEnum.Continuous})
        self._imageserver._picam2.set_controls(
            {"AfTrigger": controls.AfTriggerEnum.Start})
        try:
            self._imageserver._picam2.set_controls(
                {"AfSpeed": controls.AfSpeedEnum.Fast})
        except Exception as exc:
            logger.info(exc)
            logger.info("control not available on all cameras - can ignore")
