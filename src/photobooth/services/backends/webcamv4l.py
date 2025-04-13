"""
v4l webcam implementation backend
"""

import logging
from pathlib import Path
from tempfile import NamedTemporaryFile
from threading import Condition
from typing import TYPE_CHECKING, Literal

import cv2
from turbojpeg import TurboJPEG

from ..config.groups.backends import GroupBackendV4l2
from .abstractbackend import AbstractBackend, GeneralBytesResult

try:
    import linuxpy.video.device as linuxpy_video_device  # type: ignore
except ImportError:
    linuxpy_video_device = None

if TYPE_CHECKING:
    import linuxpy.video.device as linuxpy_video_device_type  # type: ignore

logger = logging.getLogger(__name__)
turbojpeg = TurboJPEG()


class WebcamV4lBackend(AbstractBackend):
    def __init__(self, config: GroupBackendV4l2):
        self._config: GroupBackendV4l2 = config
        super().__init__(orientation=config.orientation)

        if linuxpy_video_device is None:
            raise ModuleNotFoundError("Backend is not available - either wrong platform or not installed!")

        self._lores_data: GeneralBytesResult = GeneralBytesResult(data=b"", condition=Condition())
        self._fmt_pixel_format: linuxpy_video_device_type.PixelFormat | None = None

    def start(self):
        super().start()

        logger.debug(f"{self.__module__} started")

    def stop(self):
        super().stop()

        logger.debug(f"{self.__module__} stopped")

    def _wait_for_multicam_files(self) -> list[Path]:
        raise NotImplementedError("backend does not support multicam files")

    def _wait_for_still_file(self) -> Path:
        """
        for other threads to receive a hq JPEG image
        mode switches are handled internally automatically, no separate trigger necessary
        this function blocks until frame is received
        raise TimeoutError if no frame was received
        """

        if self._config.switch_to_high_resolution_for_stills:
            return self._wait_for_still_file_switch_hires()
        else:
            return self._wait_for_still_file_noswitch_lores()

    def _wait_for_still_file_switch_hires(self) -> Path:
        assert self._hires_data

        with self._hires_data.condition:
            self._hires_data.request.set()

            if not self._hires_data.condition.wait(timeout=4):
                # wait returns true if timeout expired
                raise TimeoutError("timeout receiving frames")

            self._hires_data.request.clear()
            assert self._hires_data.filepath

            return self._hires_data.filepath

    def _wait_for_still_file_noswitch_lores(self) -> Path:
        with NamedTemporaryFile(mode="wb", delete=False, dir="tmp", prefix="webcamv4l2_lores_", suffix=".jpg") as f:
            f.write(self._wait_for_lores_image())
            return Path(f.name)

    def _wait_for_lores_image(self) -> bytes:
        """for other threads to receive a lores JPEG image"""

        self.pause_wait_for_lores_while_hires_capture()

        with self._lores_data.condition:
            if not self._lores_data.condition.wait(timeout=0.5):
                raise TimeoutError("timeout receiving frames")

            return self._lores_data.data

    def _on_configure_optimized_for_idle(self):
        pass

    def _on_configure_optimized_for_hq_preview(self):
        pass

    def _on_configure_optimized_for_hq_capture(self):
        pass

    def _set_mode(self, capture: "linuxpy_video_device_type.VideoCapture", mode: Literal["hires", "lores"]):
        assert linuxpy_video_device
        logger.info(f"switch_mode to {mode} requested")

        if mode == "hires":
            width, height = self._config.HIRES_CAM_RESOLUTION_WIDTH, self._config.HIRES_CAM_RESOLUTION_HEIGHT
        else:
            width, height = self._config.CAM_RESOLUTION_WIDTH, self._config.CAM_RESOLUTION_HEIGHT

        try:
            capture.set_format(width, height, self._config.pixel_format)
        except Exception as exc:
            logger.error(f"error switching mode due to {exc}")

        fmt = capture.get_format()

        logger.info(f"requested {mode}-resolution is {width}x{height}, format {self._config.pixel_format}")
        logger.info(f"   actual {mode}-resolution is {fmt.width}x{fmt.height}, format {fmt.pixel_format.name}")

        # save for later use
        self._fmt_pixel_format = fmt.pixel_format

        assert self._fmt_pixel_format
        if self._fmt_pixel_format not in (
            linuxpy_video_device.PixelFormat.MJPEG,
            linuxpy_video_device.PixelFormat.JPEG,
            linuxpy_video_device.PixelFormat.YUYV,
        ):
            raise RuntimeError(
                f"Camera selected pixel_format '{fmt.pixel_format.name}', but it is not supported."
                "Your camera is probably not supported and the error permanent."
            )

        if fmt.width != width or fmt.height != height:
            logger.warning(
                f"Actual camera resolution {fmt.width}x{fmt.height} is different from requested resolution {width}x{height}! "
                "The camera might not work properly!"
            )
        if self._config.pixel_format.lower() != self._fmt_pixel_format.name.lower():
            logger.warning(
                f"Actual camera pixel_format {self._fmt_pixel_format.name} is different from requested format {self._config.pixel_format}! "
                "The camera might not work properly!"
            )

    def _frame_to_jpeg(self, frame: "linuxpy_video_device_type.Frame") -> bytes:
        """Convert JPG/MJPG and YUVY pixelformat to output JPG"""
        # https://github.com/tiagocoutinho/linuxpy/blob/d223fa2b9078fd5b0ba1415ddea5c38f938398c5/examples/video/web/common.py#L29
        assert linuxpy_video_device
        assert self._fmt_pixel_format is not None

        if self._fmt_pixel_format in (linuxpy_video_device.PixelFormat.MJPEG, linuxpy_video_device.PixelFormat.JPEG):
            return bytes(frame)
        elif self._fmt_pixel_format == linuxpy_video_device.PixelFormat.YUYV:  # v4l raw int enum 16  YUV 4:2:2
            data = frame.array
            data.shape = frame.height, frame.width, -1
            # turbojpeg.encode_from_yuv would be most efficient but needs planar data YUV, but webcam YUVY is non-planar.
            # cv2 to convert to planar YUV would be most efficient but is not avail :(
            bgr = cv2.cvtColor(data, cv2.COLOR_YUV2BGR_YUYV)
            return turbojpeg.encode(bgr, quality=90)
        else:
            raise RuntimeError(f"pixel_format {self._fmt_pixel_format} not supported")

    def _get_device(self, device_text: str | int):
        # translate id or /dev/v4l/xxx to Device
        # https://github.com/tiagocoutinho/linuxpy/blob/d223fa2b9078fd5b0ba1415ddea5c38f938398c5/examples/video/video_capture.py#L47

        assert linuxpy_video_device
        try:
            return linuxpy_video_device.Device.from_id(int(device_text))
        except ValueError:
            return linuxpy_video_device.Device(device_text)

    def setup_resource(self):
        logger.info("Connecting to resource...")

    def teardown_resource(self):
        logger.info("Disconnecting from resource...")

    def run_service(self):
        logger.info("Running service logic...")

        assert linuxpy_video_device

        logger.info(f"trying to open camera index={self._config.device_identifier=}")
        with self._get_device(self._config.device_identifier) as device:
            logger.info(f"webcam device index: {self._config.device_identifier}")
            logger.info(f"webcam name: {device.info.card if device.info else 'unknown'}")

            capture = linuxpy_video_device.VideoCapture(device)

            try:
                capture.set_fps(25)
            except OSError as exc:
                logger.warning(f"cannot set_fps due to error: {exc}")
                # continue even if error occured, camera might not support fps setting...

            while not self._stop_event.is_set():
                if self._hires_data.request.is_set():
                    # only capture one pic and return to lores streaming afterwards
                    self._hires_data.request.clear()

                    self._set_mode(capture, "hires")

                    # capture hq picture
                    skip_counter = 0
                    for frame in device:
                        # throw away the first x frames to allow the camera to settle again.
                        if skip_counter <= self._config.flush_number_frames_after_switch:
                            skip_counter += 1
                            continue

                        logger.info(f"skipped {skip_counter} frames before capture high resolution image")

                        with NamedTemporaryFile(mode="wb", delete=False, dir="tmp", prefix="webcamv4l2_hires_", suffix=".jpg") as f:
                            f.write(self._frame_to_jpeg(frame))

                        self._hires_data.filepath = Path(f.name)

                        logger.info(f"written image to {Path(f.name)}")

                        with self._hires_data.condition:
                            self._hires_data.condition.notify_all()

                        # grab just one frame...
                        break
                else:
                    self._set_mode(capture, "lores")

                    for frame in device:  # forever
                        with self._lores_data.condition:
                            self._lores_data.data = self._frame_to_jpeg(frame)
                            self._lores_data.condition.notify_all()

                        self._frame_tick()

                        # leave lores in favor to hires still capture for 1 frame.
                        if self._hires_data.request.is_set():
                            break

                        # abort streaming on shutdown so process can join and close
                        if self._stop_event.is_set():
                            break

        logger.info("v4l_img_aquisition finished, exit")
