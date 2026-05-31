"""
v4l webcam implementation backend
"""

import logging
import time
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import TYPE_CHECKING

import cv2

from ...utils.helper import filename_str_time
from ..config.groups.cameras import GroupCameraV4l2
from .abstractbackend import AbstractBackend, StillRequest

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
        super().__init__(orientation=config.orientation, num_subdevices=1)

        if linuxpy_video_device is None:
            raise ModuleNotFoundError("Backend is not available because linuxpy is not found - either wrong platform or not installed!")

        if turbojpeg is None:
            raise ModuleNotFoundError("Backend is not available because turbojpeg library is not found - either wrong platform or not installed!")

        self._device: linuxpy_video_device_type.Device | None = None
        self._capture: linuxpy_video_device_type.VideoCapture | None = None
        self._fmt_pixel_format: linuxpy_video_device_type.PixelFormat | None = None
        self._skip_frames_after_switch: int = 0

    def __str__(self):
        return f"{self.__class__.__name__}:{self._config.device_identifier}"

    def start(self):
        super().start()

    def stop(self):
        super().stop()

    def _handle_switchmode_video_mode(self):
        self._set_mode(self._config.CAM_RESOLUTION_WIDTH, self._config.CAM_RESOLUTION_HEIGHT)
        self._skip_frames_after_switch: int = 1

        super()._handle_switchmode_video_mode()

    def _handle_switchmode_still_mode(self):
        self._set_mode(self._config.HIRES_CAM_RESOLUTION_WIDTH, self._config.HIRES_CAM_RESOLUTION_HEIGHT)
        self._skip_frames_after_switch: int = 1 + self._config.flush_number_frames_after_switch

        super()._handle_switchmode_still_mode()

    def _handle_switchmode_standby(self):
        super()._handle_switchmode_standby()

    def _set_mode(self, width: int, height: int):
        assert linuxpy_video_device
        assert self._capture

        try:
            # pixel_format is handed over to v4l_fourcc, so it needs to be MJPG for MJPEG
            self._capture.set_format(width, height, self._config.pixel_format_fourcc)
        except Exception as exc:
            logger.error(f"error switching mode due to {exc}")

        fmt = self._capture.get_format()
        px_fmt_req = linuxpy_video_device.PixelFormat(linuxpy_video_device.raw.v4l2_fourcc(*self._config.pixel_format_fourcc))
        logger.info(f"requested resolution is {width}x{height}, format {px_fmt_req.name}")
        logger.info(f"   actual resolution is {fmt.width}x{fmt.height}, format {fmt.pixel_format.name}")

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

        if frame.flags & linuxpy_video_device.BufferFlag.ERROR:
            # This frame is corrupted / incomplete / non-JPEG
            raise ValueError("Camera delivered an invalid frame (ERROR flag set)")

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

    def setup_resource(self):
        assert linuxpy_video_device

        self._device = self._get_device(self._config.device_identifier)
        self._device.open()
        self._capture = linuxpy_video_device.VideoCapture(self._device)

        try:
            self._capture.set_fps(25)
        except OSError as exc:
            logger.warning(f"cannot set_fps due to error: {exc}")
            # continue even if error occured, camera might not support fps setting...

    def teardown_resource(self):
        if self._device:
            self._device.close()

    def run_service(self):
        assert linuxpy_video_device
        assert self._device
        assert self._capture

        logger.info(f"webcam device index: {self._config.device_identifier}")
        logger.info(f"webcam name: {self._device.info.card if self._device.info else 'unknown'}")

        while not self._stop_event.is_set():
            with self._hires_lock:
                req = self._hires_queue.popleft() if self._hires_queue else None

            if req:
                self._mode_machine.process_switchmode()

                if isinstance(req, StillRequest):
                    with self._capture:
                        for frame in self._capture:
                            if frame.frame_nb == 0:
                                # always flush the very first frame. some cameras might send garbage (here Insta360 Link 2C Pro)
                                continue

                            if frame.frame_nb < self._skip_frames_after_switch:
                                continue

                            logger.info(f"flushed {self._config.flush_number_frames_after_switch} frames before capture high resolution image")

                            with NamedTemporaryFile(mode="wb", delete=False, dir="tmp", prefix=f"{filename_str_time()}_v4l2_", suffix=".jpg") as f:
                                f.write(self._frame_to_jpeg(frame))

                            logger.info(f"written image to {Path(f.name)}")

                            with req.condition:
                                req.result_file = Path(f.name)
                                req.condition.notify_all()

                            # job done
                            break

                else:
                    logger.warning(f"this backend does not support {type(req)} requests")
                    continue

            self._mode_machine.process_switchmode()

            if self._mode_machine.active_mode == "standby":
                time.sleep(0.1)
                continue

            self._mode_machine.process_switchmode("video")

            with self._capture:
                for frame in self._capture:
                    if frame.frame_nb == 0:
                        # always flush the very first frame. some cameras might send garbage (here Insta360 Link 2C Pro)
                        continue

                    if frame.frame_nb < self._skip_frames_after_switch:
                        continue

                    if not self._framerate.should_process_frame(15):
                        continue

                    # produce
                    try:
                        jpeg_buffer = self._frame_to_jpeg(frame)
                    except ValueError as exc:
                        logger.debug(f"error converting frame to jpeg: {exc}")
                        continue

                    self._frame_tick()

                    with self._lores_data[0].condition:
                        self._lores_data[0].data = jpeg_buffer
                        self._lores_data[0].condition.notify_all()

                    # check for pending mode change? if so break out the stream and switch
                    if self._mode_machine.is_mode_change_pending:
                        break

                    # leave lores in favor to hires still capture for 1 frame.
                    with self._hires_lock:
                        if self._hires_queue:
                            break

                    # abort streaming on shutdown so process can join and close
                    if self._stop_event.is_set():
                        break

        logger.info("v4l_img_acquisition finished, exit")
