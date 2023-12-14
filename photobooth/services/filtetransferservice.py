import os
import shutil
import time

import psutil
from pymitter import EventEmitter
from pyudev import Context, Monitor, MonitorObserver

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
        self._context = Context()
        self._monitor = Monitor.from_netlink(self._context)
        self._monitor.filter_by(subsystem="block")
        self._observer = MonitorObserver(self._monitor, callback=self.handle_device_event)

    def start(self):
        if not self._config.file_transfer.enable_file_transfer:
            self._logger.info("FileTransferService disabled, start aborted.")
            return

        self._observer.start()
        self._logger.info("FileTransferService started.")

    def stop(self):
        self._observer.stop()
        self._logger.info("FileTransferService stopped.")

    def handle_device_event(self, device):
        if self.is_usb_device(device):
            if device.action == "add":
                usb_path = self.wait_for_mount(device.device_node)
                if usb_path and self.has_enough_space(usb_path):
                    self.copy_folders_to_usb(usb_path)
                elif usb_path:
                    self._logger.warning(f"Not enough space on USB device at {usb_path} to copy the folders.")
            elif device.action == "remove":
                self.handle_unmount(device.device_node)

    def handle_unmount(self, device_node):
        # Handle the logic when a device is unmounted
        self._logger.info(f"Device {device_node} has been removed.")

    def wait_for_mount(self, device_node, retries=10, delay=1):
        """Wait for the device to be mounted."""
        for _ in range(retries):
            mountpoint = self.get_mounted_path(device_node)
            if mountpoint:
                return mountpoint
            time.sleep(delay)
        self._logger.warning(f"Device {device_node} was not mounted after {retries} retries.")
        return None

    @staticmethod
    def is_usb_device(device):
        return device.get("ID_BUS") == "usb" and device.get("DEVTYPE") == "partition"

    def get_mounted_path(self, device_node):
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
        for root, dirs, files in os.walk(path):
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
