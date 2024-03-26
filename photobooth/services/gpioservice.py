"""
submit events on gpio pin interrups

Pin Numbering: https://gpiozero.readthedocs.io/en/stable/recipes.html#pin-numbering

"""

import subprocess

from gpiozero import Button

from ..utils.exceptions import ProcessMachineOccupiedError
from ..utils.helper import is_rpi
from .baseservice import BaseService
from .config import appconfig
from .mediacollection.mediaitem import MediaItem
from .mediacollectionservice import MediacollectionService
from .printingservice import PrintingService
from .processingservice import ProcessingService
from .sseservice import SseService

HOLD_TIME_SHUTDOWN = 2
HOLD_TIME_REBOOT = 2
DEBOUNCE_TIME = None  # due to bugs in GPIOZERO this feature cannot be used and remains to default=None


class GpioService(BaseService):
    """_summary_"""

    def __init__(
        self,
        sse_service: SseService,
        processing_service: ProcessingService,
        printing_service: PrintingService,
        mediacollection_service: MediacollectionService,
    ):
        super().__init__(sse_service=sse_service)

        self._processing_service = processing_service
        self._printing_service = printing_service
        self._mediacollection_service = mediacollection_service

        # input buttons
        self.shutdown_btn: Button = None
        self.reboot_btn: Button = None
        self.take1pic_btn: Button = None
        self.takecollage_btn: Button = None
        self.takeanimation_btn: Button = None
        self.takevideo_btn: Button = None
        self.print_recent_item_btn: Button = None

        # output signals
        # none yet

        if appconfig.hardwareinputoutput.gpio_enabled:
            if is_rpi():
                self.init_io()
                self._logger.info("gpio enabled - listeners installed")
            else:
                self._logger.info("platform is not raspberry pi - gpio library is not supported")
        else:
            if is_rpi():
                self._logger.info("gpio not enabled - enable for gpio support on raspberry pi")

    def init_io(self):
        self.shutdown_btn: Button = Button(
            appconfig.hardwareinputoutput.gpio_pin_shutdown,
            hold_time=HOLD_TIME_SHUTDOWN,
            bounce_time=DEBOUNCE_TIME,
        )
        self.reboot_btn: Button = Button(
            appconfig.hardwareinputoutput.gpio_pin_reboot,
            hold_time=HOLD_TIME_REBOOT,
            bounce_time=DEBOUNCE_TIME,
        )
        self.take1pic_btn: Button = Button(
            appconfig.hardwareinputoutput.gpio_pin_take1pic,
            bounce_time=DEBOUNCE_TIME,
        )
        self.takecollage_btn: Button = Button(
            appconfig.hardwareinputoutput.gpio_pin_collage,
            bounce_time=DEBOUNCE_TIME,
        )
        self.takeanimation_btn: Button = Button(
            appconfig.hardwareinputoutput.gpio_pin_animation,
            bounce_time=DEBOUNCE_TIME,
        )
        self.takevideo_btn: Button = Button(
            appconfig.hardwareinputoutput.gpio_pin_video,
            bounce_time=DEBOUNCE_TIME,
        )
        self.print_recent_item_btn: Button = Button(
            appconfig.hardwareinputoutput.gpio_pin_print_recent_item,
            bounce_time=DEBOUNCE_TIME,
        )

        self._register_listener()

    def start(self):
        super().set_status_started()

    def stop(self):
        super().set_status_stopped()

    def _shutdown(self):
        self._logger.info("trigger _shutdown")
        subprocess.check_call(["poweroff"])

    def _reboot(self):
        self._logger.info("trigger _reboot")
        subprocess.check_call(["reboot"])

    def _startjob(self, job):
        try:
            job()
        except ProcessMachineOccupiedError as exc:
            # raised if processingservice not idle
            self._logger.warning(f"only one capture at a time allowed, request ignored: {exc}")
        except Exception as exc:
            # other errors
            self._logger.exception(exc)
            self._logger.critical(exc)

    def _take1pic(self):
        self._logger.info("trigger _take1pic")
        self._startjob(self._processing_service.start_job_1pic)

    def _takecollage(self):
        self._logger.info("trigger _takecollage")
        self._startjob(self._processing_service.start_job_collage)

    def _takeanimation(self):
        self._logger.info("trigger _takeanimation")
        self._startjob(self._processing_service.start_job_animation)

    def _takevideo(self):
        self._logger.info("trigger _takevideo")
        self._startjob(self._processing_service.start_or_stop_job_video)

    def _print_recent_item(self):
        self._logger.info("trigger _print_recent_item")

        try:
            mediaitem: MediaItem = self._mediacollection_service.db_get_most_recent_mediaitem()
            self._printing_service.print(mediaitem=mediaitem)
        except BlockingIOError:
            self._logger.warning(f"Wait {self._printing_service.remaining_time_blocked():.0f}s until next print is possible.")
        except Exception as exc:
            # other errors
            self._logger.critical(exc)

    def _register_listener(self):
        self._register_listener_inputs()
        self._register_listener_outputs()

    def _register_listener_inputs(self):
        # shutdown
        self.shutdown_btn.when_held = self._shutdown
        # reboot
        self.reboot_btn.when_held = self._reboot
        # take single
        self.take1pic_btn.when_pressed = self._take1pic
        # take collage
        self.takecollage_btn.when_pressed = self._takecollage
        # take animation
        self.takeanimation_btn.when_pressed = self._takeanimation
        # take video
        self.takevideo_btn.when_pressed = self._takevideo
        # print
        self.print_recent_item_btn.when_pressed = self._print_recent_item

    def _register_listener_outputs(self):
        pass
