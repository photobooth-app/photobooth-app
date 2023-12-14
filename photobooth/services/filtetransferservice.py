import os
import shutil
import time

import psutil
from pymitter import EventEmitter

from photobooth.utils.stoppablethread import StoppableThread

from ..appconfig import AppConfig
from .baseservice import BaseService
from .mediacollection.mediaitem import (
    PATH_FULL,
    PATH_FULL_UNPROCESSED,
    PATH_ORIGINAL,
)


class FileTransferService(BaseService):
    def __init__(self, evtbus: EventEmitter, config: AppConfig):
        super().__init__(evtbus, config)
        self.previous_devices = self.get_current_removable_media()
        self._initialized: bool = False
        self._worker_thread = StoppableThread(name="_shareservice_worker", target=self._worker_fun, daemon=True)

    def start(self):
        if not self._config.file_transfer.enable_file_transfer:
            self._logger.info("FileTransferService disabled, start aborted.")
            return

        if not self._initialized:
            self._worker_thread.start()
            self._initialized = True

            self._logger.info("FileTransferService started.")
        else:
            self._logger.error("FileTransferService init was not successful. start service aborted.")

    def stop(self):
        self._worker_thread.stop()
        if self._worker_thread.is_alive():
            self._worker_thread.join()
        self._logger.info("FileTransferService stopped.")
        self._initialized = False

    def _worker_fun(self):
        while not self._worker_thread.stopped():
            current_devices = self.get_current_removable_media()
            added = current_devices - self.previous_devices
            removed = self.previous_devices - current_devices

            for device in added:
                usb_path = device.mountpoint
                if usb_path and self.has_enough_space(usb_path):
                    self.copy_folders_to_usb(usb_path)
                elif usb_path:
                    self._logger.warning(f"Not enough space on USB device at {usb_path} to copy the folders.")

            for device in removed:
                self.handle_unmount(device.device)

            self.previous_devices = current_devices
            time.sleep(1)  # Adjust the sleep time as needed

    def handle_unmount(self, device_node):
        self._logger.info(f"Device {device_node} has been removed.")

    @staticmethod
    def get_current_removable_media():
        return {device for device in psutil.disk_partitions(all=False)}

    @staticmethod
    def get_mounted_path(device_node):
        for part in psutil.disk_partitions():
            if part.device == device_node:
                return part.mountpoint
        return None

    def has_enough_space(self, device_path):
        _, _, free = shutil.disk_usage(device_path)
        total_size = sum(self.get_dir_size(path) for path in [PATH_ORIGINAL, PATH_FULL, PATH_FULL_UNPROCESSED])
        return free >= total_size

    @staticmethod
    def get_last_folder_name(path):
        # Strip the trailing slash if it exists
        path = path.rstrip(os.sep)
        # Return the last folder name
        return os.path.basename(path)

    @staticmethod
    def get_dir_size(path):
        total = 0
        for root, _dirs, files in os.walk(path):
            total += sum(os.path.getsize(os.path.join(root, name)) for name in files)
        return total

    def copy_folders_to_usb(self, usb_path):
        if self._config.file_transfer.usb_folder_name == "":
            self._logger.warn("Target USB parent foldername cannot be empty")
            return

        destination_path = os.path.join(usb_path, self._config.file_transfer.usb_folder_name)
        os.makedirs(destination_path, exist_ok=True)

        for folder in [PATH_ORIGINAL, PATH_FULL, PATH_FULL_UNPROCESSED]:
            shutil.copytree(folder, os.path.join(destination_path, self.get_last_folder_name(folder)), dirs_exist_ok=True)

        self._logger.info(f"Copied folders to {destination_path}")
