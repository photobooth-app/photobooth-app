"""
pyav webcam implementation backend
"""

import logging
import sys
import time
from pathlib import Path
from tempfile import NamedTemporaryFile
from threading import Condition

import av
from av.codec import Capabilities, Codec
from av.codec.codec import UnknownCodecError
from av.video.reformatter import Interpolation, VideoReformatter
from simplejpeg import encode_jpeg_yuv_planes

from ...utils.stoppablethread import StoppableThread
from ..config.groups.backends import GroupBackendPyav
from .abstractbackend import AbstractBackend, GeneralBytesResult

logger = logging.getLogger(__name__)

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
else:
    raise RuntimeError("backend not supported by platform")


class WebcamPyavBackend(AbstractBackend):
    def __init__(self, config: GroupBackendPyav):
        self._config: GroupBackendPyav = config
        super().__init__(orientation=config.orientation)

        self._lores_data: GeneralBytesResult = GeneralBytesResult(data=b"", condition=Condition())
        self._worker_thread: StoppableThread | None = None

        # for debugging purposes output some information about underlying libs
        self._version_codec_info()

    def start(self):
        super().start()

        logger.debug(f"{self.__module__} started")

    def stop(self):
        super().stop()

        logger.debug(f"{self.__module__} stopped")

    def _device_name_platform(self):
        return f"video={self._config.device_identifier}" if sys.platform == "win32" else f"{self._config.device_identifier}"

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

    def setup_resource(self):
        logger.info("Connecting to resource...")

    def teardown_resource(self):
        logger.info("Disconnecting from resource...")

    def run_service(self):
        logger.info("Running service logic...")

        reformatter = VideoReformatter()
        options = {
            "video_size": f"{self._config.cam_resolution_width}x{self._config.cam_resolution_height}",
            "input_format": "mjpeg",  # or h264 if supported is also possible but seems it has no effect (tested on windows dshow only)
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
        except Exception as exc:
            logger.exception(exc)
            logger.critical(f"cannot open camera, error {exc}. Likely the parameter set are not supported by the camera or camera name wrong.")
            time.sleep(2)  # some delay to avoid fast reiterations on a possibly non recoverable error
            return

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
            for frame in input_device.decode(input_stream):
                logger.info(f"pyav frame received: {frame}")
                logger.info(f"frame format: {frame.format}")

                break

            for frame in input_device.decode(input_stream):
                # hires
                if self._hires_data.request.is_set():
                    self._hires_data.request.clear()

                    jpeg_bytes_packet = bytes(next(input_device.demux()))

                    # only capture one pic and return to lores streaming afterwards
                    with NamedTemporaryFile(mode="wb", delete=False, dir="tmp", prefix="webcampyav_hires_", suffix=".jpg") as f:
                        f.write(jpeg_bytes_packet)

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

                jpeg_bytes = encode_jpeg_yuv_planes(
                    Y=out_frame[:rH],
                    U=out_frame.reshape(rH * 3, rW // 2)[rH * 2 : rH * 2 + rH // 2],
                    V=out_frame.reshape(rH * 3, rW // 2)[rH * 2 + rH // 2 :],
                    quality=85,
                    fastdct=True,
                )

                with self._lores_data.condition:
                    self._lores_data.data = jpeg_bytes
                    self._lores_data.condition.notify_all()

                self._frame_tick()

                # abort streaming on shutdown so process can join and close
                if self._stop_event.is_set():
                    break

        logger.info("pyav_img_aquisition finished, exit")

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
