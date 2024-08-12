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
        self._sse_service = sse_service
        self._worker_thread: StoppableThread = None

    def start(self):
        if not appconfig.filetransfer.enabled:
            self._logger.info("FileTransferService disabled, start aborted.")
            return

        self._worker_thread = StoppableThread(name="_filetransferservice_worker", target=self._worker_fun, daemon=True)
        self._worker_thread.start()

        self._logger.info("FileTransferService started.")

    def stop(self):
        if self._worker_thread and self._worker_thread.is_alive():
            self._worker_thread.stop()
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

            # poll every 1 seconds
            time.sleep(1)

    def handle_mount(self, device: psutil._common.sdiskpart):
        self._logger.info(f"Device {device.device} has been newly detected.")

        if device.mountpoint:
            if self.has_enough_space(device.mountpoint):
                self.copy_folders_to_usb(device.mountpoint)
            else:
                self._logger.warning(f"Not enough space on USB device at {device.mountpoint} to copy the folders.")
                self._sse_service.dispatch_event(
                    SseEventFrontendNotification(
                        color="negative",
                        message=f"Not enough space on USB device at {device.mountpoint} to copy the folders.",
                        caption="USB Copy Error",
                    )
                )
        else:
            self._logger.error(f"USB device not correctly mounted {device}.")

    def handle_unmount(self, device: psutil._common.sdiskpart):
        self._logger.info(f"Device {device.device} has been removed.")

    @staticmethod
    def get_current_removable_media():
        """Returns set of removable drives detected on the computer."""
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
            self._logger.warning("Target USB parent folder name cannot be empty")
            return

        destination_path = Path(usb_path, appconfig.filetransfer.target_folder_name)

        try:
            os.makedirs(destination_path, exist_ok=True)
        except Exception as exc:
            self._logger.warning(f"Error creating folder {destination_path} on USB drive: {exc}")
            self._sse_service.dispatch_event(
                SseEventFrontendNotification(
                    color="negative",
                    message=f"Error creating folder {destination_path} on USB drive: {exc}",
                    caption="USB Copy Error",
                )
            )
            return

        self._logger.info(f"Start copying data to {destination_path}")
        total_size = sum(self.get_dir_size(Path(folder)) for folder in LIST_FOLDERS_TO_COPY) / (1024 * 1024)  # Convert to MB
        copied_size = 0
        start_time = time.time()

        for folder in LIST_FOLDERS_TO_COPY:
            try:
                for item in Path(folder).rglob("*"):
                    if item.is_file():
                        destination = Path(destination_path, item.relative_to(Path(folder)))
                        destination.parent.mkdir(parents=True, exist_ok=True)
                        file_size = item.stat().st_size / (1024 * 1024)  # Convert to MB
                        shutil.copy2(item, destination)
                        copied_size += file_size
                        
                        elapsed_time = time.time() - start_time
                        estimated_total_time = (elapsed_time / copied_size) * total_size
                        remaining_time = estimated_total_time - elapsed_time

                        self._sse_service.dispatch_event(
                            SseEventFrontendNotification(
                                color="info",
                                message=(
                                    f"Copying files to USB: {copied_size:.2f}/{total_size:.2f} MB copied. "
                                    f"Estimated time remaining: {self.format_time(remaining_time)}"
                                ),
                                caption="USB Copy Progress",
                            )
                        )
            except Exception as exc:
                self._logger.warning(f"Error copying files: {exc}")
                self._sse_service.dispatch_event(
                    SseEventFrontendNotification(
                        color="negative",
                        message=f"Error copying files: {exc}",
                        caption="USB Copy Error",
                    )
                )
                return

        self._logger.info(f"Copy folders finished. Copied to {destination_path}")
        self._sse_service.dispatch_event(
            SseEventFrontendNotification(
                color="positive",
                message=f"Finished copying to {destination_path}. Total size copied: {copied_size:.2f}/{total_size:.2f} MB",
                caption="USB Copy Completed",
            )
        )

    @staticmethod
    def format_time(seconds):
        """Format time in seconds to a string in the form of H:M:S."""
        hours, remainder = divmod(int(seconds), 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{hours}h {minutes}m {seconds}s" if hours > 0 else f"{minutes}m {seconds}s"
