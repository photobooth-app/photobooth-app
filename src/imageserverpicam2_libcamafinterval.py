# pylint: disable=protected-access
"""
autofocus control using native libcamera functions
"""
import logging

try:
    from libcamera import controls
except ImportError as import_exc:
    raise OSError("libcamera not supported on windows platform") from import_exc
from pymitter import EventEmitter
from src.imageserverabstract import ImageServerAbstract
from src.repeatedtimer import RepeatedTimer
from src.configsettings import settings

logger = logging.getLogger(__name__)


class ImageServerPicam2LibcamAfInterval:
    """
    native libcamera control autofocus implementation
    usage according to official documentation chapter 5.2:
    https://datasheets.raspberrypi.com/camera/picamera2-manual.pdf

    prefer continuous mode if supported by camera module (currently only rpi camera module 3)
    if continuous mode is not available, use auto mode and trigger by timer every X seconds to focus
    option to trigger focus on thrill also possible
    """

    def __init__(self, imageserver: ImageServerAbstract, evtbus: EventEmitter):
        self._imageserver: ImageServerAbstract = imageserver

        self._evtbus = evtbus

        self._autofocus_trigger_timer_thread: RepeatedTimer = RepeatedTimer(
            interval=settings.backends.picam2_focuser_interval,
            function=self._autofocus_trigger_timer_fun,
        )
        # unmute to actually trigger focus requests:
        self._mute_cyclic_trigger_requests: bool = False

        self._evtbus.on("statemachine/on_thrill", self._on_thrill)
        self._evtbus.on("statemachine/on_exit_capture_still", self._on_capture_finished)
        self._evtbus.on("onCaptureMode", self._on_capturemode)
        self._evtbus.on("onPreviewMode", self._on_previewmode)

        logger.info(f"{__name__} initialized")

    def start(self):
        """start timer thread"""
        self._init_autofocus()
        self._autofocus_trigger_timer_thread.start()

    def stop(self):
        """stop timer thread; missing this will lead to halt on program exit."""
        self._autofocus_trigger_timer_thread.stop()

    def _autofocus_trigger_timer_fun(self):
        """_summary_"""
        if not self._mute_cyclic_trigger_requests:
            self._autofocus_cycle()

    def _on_thrill(self):
        """_summary_"""
        logger.info("called libcamautofocus _on_thrill")
        self._mute_cyclic_trigger_requests = True

    def _on_capture_finished(self):
        """_summary_"""
        logger.info("called libcamautofocus _on_capture_finished")
        self._mute_cyclic_trigger_requests = False

    def _on_capturemode(self):
        """_summary_"""
        logger.info("called libcamautofocus _on_capturemode")
        # nothing to do - should be same event as thrilled

    def _on_previewmode(self):
        """_summary_"""
        logger.info("called libcamautofocus _on_previewmode")
        # nothing to do - should be same event as capture finished

    def _init_autofocus(self):
        """
        on start one time autofocus
        and trigger regularly
        """
        try:
            self._imageserver._picam2.set_controls(
                {"AfSpeed": controls.AfSpeedEnum.Fast}
            )
            logger.info("libcamautofocus AfSpeed set to fast mode")
        except RuntimeError as exc:
            logger.info(f"control not available on all cameras - can ignore {exc}")

    def _autofocus_cycle(self):
        try:
            # success = self._imageserver._picam2.autofocus_cycle(wait=False)
            # this command breaks the frameserver - reason not yet clear, so currently
            # autofocus invoked like this:
            self._imageserver._picam2.set_controls(
                {
                    "AfMode": controls.AfModeEnum.Auto,
                    "AfTrigger": controls.AfTriggerEnum.Start,
                }
            )
        except RuntimeError as exc:
            logger.critical(
                f"control not available on camera - autofocus not working properly {exc}"
            )
