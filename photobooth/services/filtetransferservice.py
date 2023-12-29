import os
import shutil
import time
from pathlib import Path

import psutil

from photobooth.utils.stoppablethread import StoppableThread

from .baseservice import BaseService
from .config import appconfig
from .mediacollection.mediaitem import (
    PATH_FULL,
    PATH_FULL_UNPROCESSED,
    PATH_ORIGINAL,
)
from .sseservice import SseService

LIST_FOLDERS_TO_COPY = [PATH_ORIGINAL, PATH_FULL, PATH_FULL_UNPROCESSED]


class FileTransferService(BaseService):
    def __init__(self, sse_service: SseService):
        super().__init__(sse_service)

        self._worker_thread: StoppableThread = None

    def start(self):
        if not appconfig.filetransfer.enabled:
            self._logger.info("FileTransferService disabled, start aborted.")
            return

        self._worker_thread = StoppableThread(name="_filetransferservice_worker", target=self._worker_fun, daemon=True)
        self._worker_thread.start()

        self._logger.info("FileTransferService started.")

    def stop(self):
        if self._worker_thread:
            self._worker_thread.stop()
            if self._worker_thread.is_alive():
                self._worker_thread.join()

        self._logger.info("FileTransferService stopped.")

    def _worker_fun(self):
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

            # poll every 4 seconds
            time.sleep(4)

    def handle_mount(self, device: psutil._common.sdiskpart):
        self._logger.info(f"Device {device.device} has been newly detected.")

        if device.mountpoint:
            if self.has_enough_space(device.mountpoint):
                self.copy_folders_to_usb(device.mountpoint)
            else:
                self._logger.warning(f"Not enough space on USB device at {device.mountpoint} to copy the folders.")
        else:
            self._logger.error(f"USB device not correctly mounted {device}.")

    def handle_unmount(self, device: psutil._common.sdiskpart):
        self._logger.info(f"Device {device.device} has been removed.")

    @staticmethod
    def get_current_removable_media():
        """Returns set of removable drives detected on the computer."""
        return {device for device in psutil.disk_partitions(all=False) if "removable" in device.opts}

    def has_enough_space(self, device_path):
        _, _, free = shutil.disk_usage(device_path)
        total_size = sum(self.get_dir_size(Path(path)) for path in LIST_FOLDERS_TO_COPY)
        return free >= total_size

    @staticmethod
    def get_dir_size(path: Path):
        return sum(f.stat().st_size for f in path.glob("**/*") if f.is_file())

    def copy_folders_to_usb(self, usb_path):
        if not appconfig.filetransfer.target_folder_name:
            self._logger.warn("Target USB parent foldername cannot be empty")
            return

        destination_path = Path(usb_path, appconfig.filetransfer.target_folder_name)

        try:
            os.makedirs(destination_path, exist_ok=True)
        except Exception as exc:
            self._logger.warning(f"Error creating folder {destination_path} on usb drive: {exc}")

        self._logger.info(f"Start copying data to {destination_path}")
        for folder in LIST_FOLDERS_TO_COPY:
            try:
                # TODO: improve to only copy modified files.
                shutil.copytree(folder, Path(destination_path, folder), dirs_exist_ok=True)
            except Exception as exc:
                self._logger.warning(f"Error copying files: {exc}")
                return

        self._logger.info(f"Copy folders finished. Copied to {destination_path}")
