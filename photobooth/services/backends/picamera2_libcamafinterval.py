# pylint: disable=protected-access
"""
autofocus control using native libcamera functions
"""
import logging
import time

try:
    from libcamera import controls
except Exception as import_exc:
    raise OSError("libcamera not supported on windows platform") from import_exc

from photobooth.services.backends.abstractbackend import AbstractBackend

from ...appconfig import AppConfig
from ...utils.repeatedtimer import RepeatedTimer

logger = logging.getLogger(__name__)


class Picamera2LibcamAfInterval:
    """
    native libcamera control autofocus implementation
    usage according to official documentation chapter 5.2:
    https://datasheets.raspberrypi.com/camera/picamera2-manual.pdf

    prefer continuous mode if supported by camera module (currently only rpi camera module 3)
    if continuous mode is not available, use auto mode and trigger by timer every X seconds to focus
    option to trigger focus on thrill also possible
    """

    def __init__(self, backend: AbstractBackend, config: AppConfig):
        self._backend: AbstractBackend = backend
        self._config = config

        self._autofocus_trigger_timer_thread: RepeatedTimer = RepeatedTimer(
            interval=self._config.backends.picamera2_focuser_interval,
            function=self._autofocus_trigger_timer_fun,
        )
        # unmute to actually trigger focus requests:
        self._mute_cyclic_trigger_requests: bool = False

        logger.info(f"{__name__} initialized")

    def start(self):
        """start timer thread"""
        self._init_autofocus()
        self._autofocus_trigger_timer_thread.start()

    def stop(self):
        """stop timer thread; missing this will lead to halt on program exit."""
        self._autofocus_trigger_timer_thread.stop()

    def ensure_focused(self):
        """Use to ensure focus is finished (or cancel/failed if no success) before capture."""
        # interval can only cancel current focus run if active
        # currently no reliable way to receive the current focus state until capture_metadata is reimplemented again.
        self._backend._picamera2.set_controls({"AfTrigger": controls.AfTriggerEnum.Cancel})

        # wait typical time, the motor needs to move back to previous position
        time.sleep(0.04)

    def on_capturemode(self):
        """_summary_"""
        logger.info("called libcamafinterval on_capturemode")
        self._mute_cyclic_trigger_requests = True
        logger.info("autofocus trigger request muted")

    def on_previewmode(self):
        """_summary_"""
        logger.info("called libcamafinterval on_previewmode")
        self._mute_cyclic_trigger_requests = False
        logger.info("autofocus trigger request unmuted")

    def _autofocus_trigger_timer_fun(self):
        """_summary_"""
        if not self._mute_cyclic_trigger_requests:
            logger.info("autofocus trigger request ignored because muted in capture mode")
            self._autofocus_cycle()

    def _init_autofocus(self):
        """
        on start one time autofocus
        and trigger regularly
        """
        try:
            self._backend._picamera2.set_controls({"AfSpeed": controls.AfSpeedEnum.Fast})
            logger.info("libcamautofocus AfSpeed set to fast mode")
        except RuntimeError as exc:
            logger.info(f"control not available on all cameras - can ignore {exc}")

    def _autofocus_cycle(self):
        try:
            self._backend._picamera2.autofocus_cycle(wait=False)
        except RuntimeError as exc:
            logger.critical(f"control not available on camera - autofocus not working properly {exc}")
