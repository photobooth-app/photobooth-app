"""
v4l webcam implementation backend
"""

import logging
from pathlib import Path
from tempfile import NamedTemporaryFile
from threading import Condition
from typing import TYPE_CHECKING, Literal

import cv2

from ...utils.helper import filename_str_time
from ..config.groups.cameras import GroupCameraV4l2
from .abstractbackend import AbstractBackend, GeneralBytesResult

try:
    import linuxpy.video.device as linuxpy_video_device  # type: ignore
except ImportError:
    linuxpy_video_device = None

if TYPE_CHECKING:
    import linuxpy.video.device as linuxpy_video_device_type  # type: ignore

try:
    # try to import the mandatory turbojpeg for this backend. it's guarded so reading this module on app init
    # doesn't fail for example on windows where turbojpeg libs doesn't need to be installed.
    # during backend init, check for None and fail if None.
    from turbojpeg import TurboJPEG

    turbojpeg = TurboJPEG()
except Exception:
    turbojpeg = None

logger = logging.getLogger(__name__)


class WebcamV4lBackend(AbstractBackend):
    def __init__(self, config: GroupCameraV4l2):
        self._config: GroupCameraV4l2 = config
        super().__init__(orientation=config.orientation)

        if linuxpy_video_device is None:
            raise ModuleNotFoundError("Backend is not available because linuxpy is not found - either wrong platform or not installed!")

        if turbojpeg is None:
            raise ModuleNotFoundError("Backend is not available because turbojpeg library is not found - either wrong platform or not installed!")

        self._lores_data: GeneralBytesResult = GeneralBytesResult(data=b"", condition=Condition())
        self._fmt_pixel_format: linuxpy_video_device_type.PixelFormat | None = None

    def start(self):
        super().start()

    def stop(self):
        super().stop()

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
        with NamedTemporaryFile(mode="wb", delete=False, dir="tmp", prefix=f"{filename_str_time()}_v4l2lores_", suffix=".jpg") as f:
            f.write(self._wait_for_lores_image())
            return Path(f.name)

    def _wait_for_lores_image(self, index_subdevice: int = 0) -> bytes:
        if index_subdevice > 0:
            raise RuntimeError("streaming from subdevices > 0 is not supported on this backend.")

        self.pause_wait_for_lores_while_hires_capture()

        with self._lores_data.condition:
            if not self._lores_data.condition.wait(timeout=0.5):
                raise TimeoutError("timeout receiving frames")

            return self._lores_data.data

    def _on_configure_optimized_for_idle(self): ...

    def _on_configure_optimized_for_hq_preview(self): ...

    def _on_configure_optimized_for_hq_capture(self): ...

    def _on_configure_optimized_for_livestream_paused(self): ...

    def _set_mode(self, capture: "linuxpy_video_device_type.VideoCapture", mode: Literal["hires", "lores"]):
        assert linuxpy_video_device
        logger.info(f"switch_mode to {mode} requested")

        if mode == "hires":
            width, height = self._config.HIRES_CAM_RESOLUTION_WIDTH, self._config.HIRES_CAM_RESOLUTION_HEIGHT
        else:
            width, height = self._config.CAM_RESOLUTION_WIDTH, self._config.CAM_RESOLUTION_HEIGHT

        try:
            # pixel_format is handed over to v4l_fourcc, so it needs to be MJPG for MJPEG
            capture.set_format(width, height, self._config.pixel_format_fourcc)
        except Exception as exc:
            logger.error(f"error switching mode due to {exc}")

        fmt = capture.get_format()

        logger.info(f"requested {mode}-resolution is {width}x{height}, format {self._config.pixel_format_fourcc}")
        logger.info(f"   actual {mode}-resolution is {fmt.width}x{fmt.height}, format {fmt.pixel_format.name}")

        # save for later use
        self._fmt_pixel_format = fmt.pixel_format

        assert self._fmt_pixel_format
        if self._fmt_pixel_format not in (
            linuxpy_video_device.PixelFormat.MJPEG,
            linuxpy_video_device.PixelFormat.JPEG,
            linuxpy_video_device.PixelFormat.YUYV,
            linuxpy_video_device.PixelFormat.YUV420,
        ):
            raise RuntimeError(
                f"Camera selected pixel_format '{self._fmt_pixel_format.name}', but it is not supported."
                "Your camera is probably not supported and the error permanent."
            )

        if fmt.width != width or fmt.height != height:
            logger.warning(
                f"Actual camera resolution {fmt.width}x{fmt.height} is different from requested resolution {width}x{height}! "
                "You should consider to set a proper resolution for the camera!"
            )
        if linuxpy_video_device.raw.v4l2_fourcc(*self._config.pixel_format_fourcc) != self._fmt_pixel_format:
            logger.warning(
                f"Actual camera pixel_format {self._fmt_pixel_format.name} is different from requested format {self._config.pixel_format_fourcc}! "
                "You should consider to select the correct pixel format!"
            )

    def _frame_to_jpeg(self, frame: "linuxpy_video_device_type.Frame") -> bytes:
        """Convert JPG/MJPG and YUVY pixelformat to output JPG"""
        # https://github.com/tiagocoutinho/linuxpy/blob/d223fa2b9078fd5b0ba1415ddea5c38f938398c5/examples/video/web/common.py#L29
        assert linuxpy_video_device
        assert self._fmt_pixel_format is not None
        assert turbojpeg

        if self._fmt_pixel_format in (linuxpy_video_device.PixelFormat.MJPEG, linuxpy_video_device.PixelFormat.JPEG):
            return bytes(frame)
        elif self._fmt_pixel_format == linuxpy_video_device.PixelFormat.YUV420:  # v4l raw int enum 12  YUV 4:2:0
            # h, w = frame.height, frame.width
            # arr = frame.array
            # Y = arr[0 : h * w].reshape((h, w))
            # U = arr[h * w : h * w + (h // 2) * (w // 2)].reshape((h // 2, w // 2))
            # V = arr[h * w + (h // 2) * (w // 2) :].reshape((h // 2, w // 2))
            # encoded = simplejpeg.encode_jpeg_yuv_planes(Y=Y, U=U, V=V, quality=85, fastdct=True)

            h, w = frame.height, frame.width
            yuv = frame.array.tobytes()  # ensure contiguous bytes
            encoded = turbojpeg.encode_from_yuv(yuv, h, w, quality=90)
            assert isinstance(encoded, bytes), "Expected bytes from turbojpeg.encode"
            return encoded
        elif self._fmt_pixel_format == linuxpy_video_device.PixelFormat.YUYV:  # v4l raw int enum 16  YUV 4:2:2
            data = frame.array
            data.shape = frame.height, frame.width, -1
            # turbojpeg.encode_from_yuv would be most efficient but needs planar data YUV, but webcam YUVY is non-planar.
            # cv2 to convert to planar YUV would be most efficient but is not avail :(
            bgr = cv2.cvtColor(data, cv2.COLOR_YUV2BGR_YUYV)
            encoded = turbojpeg.encode(bgr, quality=90)
            assert isinstance(encoded, bytes), "Expected bytes from turbojpeg.encode"
            return encoded
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

    def setup_resource(self): ...

    def teardown_resource(self): ...

    def run_service(self):
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

                        with NamedTemporaryFile(mode="wb", delete=False, dir="tmp", prefix=f"{filename_str_time()}_v4l2hires_", suffix=".jpg") as f:
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

        logger.info("v4l_img_acquisition finished, exit")
