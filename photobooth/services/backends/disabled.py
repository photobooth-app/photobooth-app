"""
v4l webcam implementation backend
"""
import logging
import time

from .abstractbackend import AbstractBackend

logger = logging.getLogger(__name__)


class DisabledBackend(AbstractBackend):
    def __init__(self):
        super().__init__()

    def _device_start(self):
        logger.debug(f"{self.__module__} start requested; doing nothing")

    def _device_stop(self):
        logger.debug(f"{self.__module__} stop requested; doing nothing")

    def _device_available(self) -> bool:
        logger.debug(f"{self.__module__} availability requested; returning False")
        return True

    def wait_for_hq_image(self):
        logger.debug(f"{self.__module__} cannot return valid images.")
        time.sleep(0.5)
        raise ValueError(f"{self.__module__} cannot return valid images.")

    def _wait_for_lores_image(self):
        time.sleep(0.2)
        raise ValueError(f"{self.__module__} cannot return valid images.")

    def _on_capture_mode(self):
        logger.debug("change to capture mode requested - ignored on this backend")

    def _on_preview_mode(self):
        logger.debug("change to preview mode requested - ignored on this backend")
