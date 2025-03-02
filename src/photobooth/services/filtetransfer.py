import logging
import os
import shutil
import time
from pathlib import Path

import psutil
from psutil import _common

from photobooth.utils.stoppablethread import StoppableThread

from .. import PATH_PROCESSED, PATH_UNPROCESSED
from ..appconfig import appconfig
from .base import BaseService

logger = logging.getLogger(__name__)
LIST_FOLDERS_TO_COPY = [PATH_UNPROCESSED, PATH_PROCESSED]


class FileTransferService(BaseService):
    def __init__(self):
        super().__init__()

        self._worker_thread: StoppableThread | None = None

    def start(self):
        super().start()

        if not appconfig.filetransfer.enabled:
            logger.info("FileTransferService disabled, start aborted.")
            super().disabled()
            return

        self._worker_thread = StoppableThread(name="_filetransferservice_worker", target=self._worker_fun, daemon=True)
        self._worker_thread.start()

        logger.info("FileTransferService started.")

        super().started()

    def stop(self):
        super().stop()

        if self._worker_thread and self._worker_thread.is_alive():
            self._worker_thread.stop()
            self._worker_thread.join()

        logger.info("FileTransferService stopped.")
        super().stopped()

    def _worker_fun(self):
        assert self._worker_thread
        # init worker, get devices first time
        _previous_devices = self.get_current_removable_media()

        while not self._worker_thread.stopped():
            current_devices = self.get_current_removable_media()
            added = current_devices - _previous_devices
            removed = _previous_devices - current_devices

            for device in added:
                self.handle_mount(device)

            for device in removed:
                self.handle_unmount(device)

            _previous_devices = current_devices

            # poll every 1 seconds
            time.sleep(1)

    def handle_mount(self, device: _common.sdiskpart):
        logger.info(f"Device {device.device} has been newly detected.")

        if device.mountpoint:
            if self.has_enough_space(device.mountpoint):
                self.copy_folders_to_usb(device.mountpoint)
            else:
                logger.warning(f"Not enough space on USB device at {device.mountpoint} to copy the folders.")
        else:
            logger.error(f"USB device not correctly mounted {device}.")

    def handle_unmount(self, device: _common.sdiskpart):
        logger.info(f"Device {device.device} has been removed.")

    @staticmethod
    def get_current_removable_media():
        """Returns set of removable drives detected on the  computer."""
        return {device for device in psutil.disk_partitions(all=False)}

    def has_enough_space(self, device_path):
        _, _, free = shutil.disk_usage(device_path)
        total_size = sum(self.get_dir_size(Path(path)) for path in LIST_FOLDERS_TO_COPY)
        return free >= total_size

    @staticmethod
    def get_dir_size(path: Path):
        return sum(f.stat().st_size for f in path.glob("**/*") if f.is_file())

    def copy_folders_to_usb(self, usb_path):
        if not appconfig.filetransfer.target_folder_name:
            logger.warning("Target USB parent foldername cannot be empty")
            return

        destination_path = Path(usb_path, appconfig.filetransfer.target_folder_name)

        try:
            os.makedirs(destination_path, exist_ok=True)
        except Exception as exc:
            logger.warning(f"Error creating folder {destination_path} on usb drive: {exc}")

        logger.info(f"Start copying data to {destination_path}")
        for folder in LIST_FOLDERS_TO_COPY:
            try:
                shutil.copytree(folder, Path(destination_path, folder), dirs_exist_ok=True)
            except Exception as exc:
                logger.warning(f"Error copying files: {exc}")
                return

        logger.info(f"Copy folders finished. Copied to {destination_path}")
