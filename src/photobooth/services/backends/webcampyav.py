"""
pyav webcam implementation backend
"""

import io
import logging
import sys
from pathlib import Path
from tempfile import NamedTemporaryFile
from threading import Condition

import av
from av.codec import Capabilities, Codec
from av.codec.codec import UnknownCodecError
from av.video.reformatter import Interpolation, VideoReformatter
from simplejpeg import encode_jpeg_yuv_planes

from ...utils.helper import filename_str_time
from ...utils.resilientservice import PermanentFault
from ...utils.stoppablethread import StoppableThread
from ..config.groups.cameras import GroupCameraPyav
from .abstractbackend import AbstractBackend, GeneralBytesResult

# Pyright cannot resolve attributes on the `av` module in some environments.
# Import av.error symbols explicitly and fall back to builtins to keep runtime behavior.
try:
    from av.error import BlockingIOError as AvBlockingIOError
    from av.error import OSError as AvOSError
except Exception:  # pragma: no cover - fallback for static analysis environments
    AvOSError = OSError
    AvBlockingIOError = BlockingIOError

logger = logging.getLogger(__name__)

input_ffmpeg_device = None
# determine the input device based on platform
if sys.platform == "win32":
    # https://ffmpeg.org/ffmpeg-devices.html#dshow  https://trac.ffmpeg.org/wiki/DirectShow
    input_ffmpeg_device = "dshow"
elif sys.platform == "darwin":
    # https://ffmpeg.org/ffmpeg-devices.html#avfoundation
    input_ffmpeg_device = "avfoundation"
elif sys.platform == "linux":
    # https://ffmpeg.org/ffmpeg-devices.html#video4linux2_002c-v4l2
    input_ffmpeg_device = "v4l2"


class WebcamPyavBackend(AbstractBackend):
    def __init__(self, config: GroupCameraPyav):
        self._config: GroupCameraPyav = config
        super().__init__(orientation=config.orientation)

        self._lores_data: GeneralBytesResult = GeneralBytesResult(data=b"", condition=Condition())
        self._worker_thread: StoppableThread | None = None

        # for debugging purposes output some information about underlying libs
        self._version_codec_info()

    def start(self):
        super().start()

        # not supported platform, will raise exception during startup. no exception during init to not break the overall app
        assert input_ffmpeg_device is not None, "the platform is not supported"

    def stop(self):
        super().stop()

    def _device_name_platform(self):
        if sys.platform == "win32":
            return f"video={self._config.device_identifier}"

        if sys.platform == "darwin":
            ident = str(self._config.device_identifier)
            if ident.isdigit():
                return ident

            try:
                device_id = self._darwin_device_index(ident)
                return str(device_id)
            except Exception:
                logger.warning("could not map camera name to avfoundation index, falling back to provided identifier")
                return f"{self._config.device_identifier}"

        return f"{self._config.device_identifier}"

    def _darwin_device_index(self, camera_name: str) -> str:
        """Map macOS camera name to avfoundation index via ffmpeg."""
        import re
        import subprocess

        try:
            proc = subprocess.run(["ffmpeg", "-f", "avfoundation", "-list_devices", "true", "-i", ""], capture_output=True, text=True, check=False)
        except FileNotFoundError as exc:
            raise RuntimeError("ffmpeg not found, cannot enumerate avfoundation devices") from exc

        stderr = proc.stderr or ""
        matches = re.findall(r"\[([0-9]+)\]\s*(.+)$", stderr, flags=re.MULTILINE)
        for idx, name in matches:
            if name.strip().lower() == camera_name.strip().lower():
                return idx

        raise RuntimeError(f"could not find avfoundation device index for camera name '{camera_name}'")

    def _wait_for_multicam_files(self) -> list[Path]:
        raise NotImplementedError("backend does not support multicam files")

    def _wait_for_still_file(self) -> Path:
        """
        for other threads to receive a hq JPEG image
        mode switches are handled internally automatically, no separate trigger necessary
        this function blocks until frame is received
        raise TimeoutError if no frame was received
        """
        with self._hires_data.condition:
            self._hires_data.request.set()

            if not self._hires_data.condition.wait(timeout=4):
                # wait returns true if timeout expired
                raise TimeoutError("timeout receiving frames")

            self._hires_data.request.clear()
            assert self._hires_data.filepath

            return self._hires_data.filepath

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

    def setup_resource(self): ...

    def teardown_resource(self): ...

    def run_service(self):
        reformatter = VideoReformatter()
        options = {
            "video_size": f"{self._config.cam_resolution_width}x{self._config.cam_resolution_height}",
        }
        if self._config.cam_framerate > 0:
            # avfoundation has ntsc as default. webcams refuse to work with that framerate, so allow to set it explicit
            # dshow/v4l usually dont need this configured because their default seems reasonable.
            options["framerate"] = str(self._config.cam_framerate)

        rW = self._config.cam_resolution_width // self._config.preview_resolution_reduce_factor
        rH = self._config.cam_resolution_height // self._config.preview_resolution_reduce_factor
        frame_count = 0

        try:
            logger.info(f"trying to open camera index={self._config.device_identifier=}")
            input_device = av.open(self._device_name_platform(), format=input_ffmpeg_device, options=options)
        except AvOSError as exc:
            # Errno 5 => Input/output error, commonly caused by unsupported framerate/resolution
            if getattr(exc, "errno", None) == 5:
                error_msg = (
                    f"Cannot open camera with current settings (resolution: {self._config.cam_resolution_width}x{self._config.cam_resolution_height}"
                    + (f", framerate: {self._config.cam_framerate}" if self._config.cam_framerate > 0 else "")
                    + "). The camera likely does not support these parameters. Try reducing the framerate or resolution in the camera settings."
                )
                logger.critical(error_msg)

                # 1) Try without explicit framerate (some devices reject an explicit framerate)
                if "framerate" in options:
                    logger.info("Retrying without explicit framerate setting...")
                    opts_fb = options.copy()
                    opts_fb.pop("framerate", None)
                    try:
                        input_device = av.open(self._device_name_platform(), format=input_ffmpeg_device, options=opts_fb)
                        logger.warning("Camera opened successfully without framerate option. Consider removing the framerate configuration.")
                    except Exception:
                        # fallthrough to trying reduced framerates
                        input_device = None
                else:
                    input_device = None

                # 2) Try a few common lower framerates
                if input_device is None:
                    for fps in (30, 25, 15):
                        if self._config.cam_framerate and fps >= self._config.cam_framerate:
                            continue
                        logger.info(f"Retrying with reduced framerate={fps}...")
                        opts_low = options.copy()
                        opts_low["framerate"] = str(fps)
                        try:
                            input_device = av.open(self._device_name_platform(), format=input_ffmpeg_device, options=opts_low)
                            logger.warning(f"Camera opened with reduced framerate={fps}. Update config to avoid repeated retries.")
                            break
                        except Exception:
                            input_device = None

                if input_device is None:
                    raise RuntimeError(error_msg) from exc
            else:
                logger.critical(f"cannot open camera, error {exc}. Likely the parameter set are not supported by the camera or camera name wrong.")
                raise
        except Exception as exc:
            logger.critical(f"cannot open camera, error {exc}. Likely the parameter set are not supported by the camera or camera name wrong.")
            raise exc

        with input_device:
            input_stream = input_device.streams.video[0]
            # shall speed up processing, ... lets keep an eye on this one...
            input_stream.thread_type = "AUTO"
            input_stream.thread_count = 0

            # 1 loop to spit out packet and frame information
            logger.info(f"input_device: {input_device}")
            logger.info(f"input_stream: {input_stream}")
            logger.info(f"input_stream codec: {input_stream.codec}")
            logger.info(f"input_stream pix_fmt: {input_stream.pix_fmt}")
            logger.info(f"pyav packet received: {next(input_device.demux())}")
            logger.info(f"livestream resolution: {rW}x{rH}")

            try:
                frame = next(input_device.decode(input_stream))
                logger.info(f"pyav frame received: {frame}")
                logger.info(f"frame format: {frame.format}")
            except Exception as exc:
                raise PermanentFault("Error decoding camera frame! Ensure the settings are correct (device name, fps, resolution, ...)") from exc

            codec_name = input_stream.codec.name

            # Main decode loop
            while not self._stop_event.is_set():
                try:
                    frame = next(input_device.decode(input_stream))
                except AvBlockingIOError:
                    # Temporary EAGAIN on macOS - just continue
                    continue
                except StopIteration:
                    # Stream ended
                    break

                # hires
                if self._hires_data.request.is_set():
                    self._hires_data.request.clear()

                    if codec_name == "mjpeg":
                        jpeg_bytes_hires = bytes(next(input_device.demux()))
                    elif codec_name == "rawvideo":
                        image_bytesio = io.BytesIO()
                        frame.to_image().save(image_bytesio, format="JPEG", quality=90)
                        jpeg_bytes_hires = image_bytesio.getvalue()
                    else:
                        raise PermanentFault(f"The webcam's codec {codec_name} is not supported!")

                    # only capture one pic and return to lores streaming afterwards
                    with NamedTemporaryFile(mode="wb", delete=False, dir="tmp", prefix=f"{filename_str_time()}_pyav_", suffix=".jpg") as f:
                        f.write(jpeg_bytes_hires)

                    self._hires_data.filepath = Path(f.name)
                    with self._hires_data.condition:
                        self._hires_data.condition.notify_all()

                # lores stream
                frame_count += 1
                if frame_count < self._config.frame_skip_count:
                    continue
                else:
                    frame_count = 0

                if self._config.preview_resolution_reduce_factor > 1:
                    out_frame = reformatter.reformat(frame, width=rW, height=rH, interpolation=Interpolation.BILINEAR, format="yuvj420p").to_ndarray()
                else:
                    if frame.format.name != "yuvj420p":
                        out_frame = reformatter.reformat(frame, format="yuvj420p").to_ndarray()
                    else:
                        out_frame = frame.to_ndarray()

                # compress raw YUV420p to JPEG
                jpeg_bytes = encode_jpeg_yuv_planes(
                    Y=out_frame[:rH],
                    U=out_frame.reshape(rH * 3, rW // 2)[rH * 2 : rH * 2 + rH // 2],
                    V=out_frame.reshape(rH * 3, rW // 2)[rH * 2 + rH // 2 :],
                    quality=85,
                    fastdct=True,
                )
                # Alternative approach using turbojpeg. speed is actually the same but simplejpeg comes with turbojpeg libs bundled for windows
                # jpeg_bytes = turbojpeg.encode_from_yuv(out_frame, rH, rW, quality=85, flags=TJFLAG_FASTDCT)

                with self._lores_data.condition:
                    self._lores_data.data = jpeg_bytes
                    self._lores_data.condition.notify_all()

                self._frame_tick()

                # abort streaming on shutdown so process can join and close
                if self._stop_event.is_set():
                    break

        logger.info("pyav_img_acquisition finished, exit")

    def _version_codec_info(self):
        logger.info(f"PyAv location {av.__file__}, package version {av.__version__}")
        logger.info(f"PyAv uses ffmpeg version {av.ffmpeg_version_info}")
        logger.info(f"PyAv library versions: {av.library_versions}")

        for codec in av.codecs_available:
            try:
                o_codec = Codec(codec, "w")  # choose codec for writing otherwise it's decoders
            except UnknownCodecError:
                pass
            else:
                if "264" in o_codec.name:
                    capabs = []
                    for cap in Capabilities:
                        if o_codec.capabilities & cap.value:
                            capabs.append(cap.name)

                    logger.debug(f"- {o_codec.name} | {o_codec.long_name} | Hardware: {'hardware' in capabs} | Capabilities: {capabs}")
