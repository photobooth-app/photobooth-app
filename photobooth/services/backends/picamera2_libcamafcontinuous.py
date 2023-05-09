# pylint: disable=protected-access
"""
autofocus control using native libcamera functions
"""
import logging

from ...appconfig import AppConfig

try:
    from libcamera import controls
except Exception as import_exc:
    raise OSError("libcamera not supported on windows platform") from import_exc
from pymitter import EventEmitter

from photobooth.services.backends.abstractbackend import AbstractBackend

logger = logging.getLogger(__name__)


class Picamera2LibcamAfContinuous:
    """
    native libcamera control autofocus implementation
    usage according to official documentation chapter 5.2:
    https://datasheets.raspberrypi.com/camera/picamera2-manual.pdf

    continuous mode needs to be supported by camera module (currently only rpi camera module 3)
    if continuous mode is not available, use auto mode and trigger by timer every X seconds to focus
    option to trigger focus on thrill also possible
    """

    def __init__(
        self, imageserver: AbstractBackend, evtbus: EventEmitter, config: AppConfig
    ):
        self._imageserver: AbstractBackend = imageserver

        self._config = config
        self._evtbus = evtbus
        self._evtbus.on("statemachine/on_thrill", self._on_thrill)
        self._evtbus.on("statemachine/on_exit_capture_still", self._on_capture_finished)
        self._evtbus.on("onCaptureMode", self._on_capturemode)
        self._evtbus.on("onPreviewMode", self._on_previewmode)

        logger.info(f"{__name__} initialized")

    def start(self):
        """start backend"""
        self._init_autofocus()

    def stop(self):
        """stop backend"""

    def _on_thrill(self):
        """nothing to do in continous mode here"""

    def _on_capture_finished(self):
        """nothing to do in continous mode here"""
        self._init_autofocus()

    def _on_capturemode(self):
        """nothing to do in continous mode here"""

    def _on_previewmode(self):
        """nothing to do in continous mode here"""

    def _init_autofocus(self):
        """
        on start set autofocus to continuous if requested by config or
        auto and trigger regularly
        """
        logger.info(f"{__name__} _init_autofocus call")
        try:
            self._imageserver._picamera2.set_controls(
                {"AfMode": controls.AfModeEnum.Continuous}
            )
            logger.info("libcamautofocus set to continuous mode")
        except RuntimeError as exc:
            logger.critical(
                f"control not available on camera - autofocus not working properly {exc}"
            )

        try:
            self._imageserver._picamera2.set_controls(
                {"AfSpeed": controls.AfSpeedEnum.Fast}
            )
            logger.info("libcamautofocus AfSpeed set to fast mode")
        except RuntimeError as exc:
            logger.info(f"control not available on all cameras - can ignore {exc}")
