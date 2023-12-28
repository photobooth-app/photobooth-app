"""
v4l webcam implementation backend
"""
import logging

from .abstractbackend import AbstractBackend

logger = logging.getLogger(__name__)


class DisabledBackend(AbstractBackend):
    def __init__(self):
        super().__init__()

    def start(self):
        logger.debug(f"{self.__module__} start requested; doing nothing")

    def stop(self):
        logger.debug(f"{self.__module__} stop requested; doing nothing")

    def wait_for_hq_image(self):
        logger.debug(f"{self.__module__} cannot return valid images.")
        raise RuntimeError(f"{self.__module__} cannot return valid images.")

    def _wait_for_lores_image(self):
        raise RuntimeError(f"{self.__module__} cannot return valid images.")

    def _on_capture_mode(self):
        logger.debug("change to capture mode requested - ignored on this backend")

    def _on_preview_mode(self):
        logger.debug("change to preview mode requested - ignored on this backend")
