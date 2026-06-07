"""
pyav webcam implementation backend
"""

import io
import logging
import sys
import time
from pathlib import Path
from tempfile import NamedTemporaryFile

import av
from av.codec import Capabilities, Codec
from av.codec.codec import UnknownCodecError
from av.video.reformatter import ColorRange, Interpolation, VideoReformatter
from simplejpeg import encode_jpeg_yuv_planes

from ...utils.helper import filename_str_time
from ...utils.resilientservice import PermanentFault
from ..config.groups.cameras import GroupCameraPyav
from .abstractbackend import AbstractBackend, StillRequest

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
        super().__init__(
            orientation=config.orientation,
            num_subdevices=1,
            idle_timeout=self._config.camera_standby_when_inactive_time if self._config.camera_standby_when_inactive else None,
        )

        # for debugging purposes output some information about underlying libs
        self._version_codec_info()

    def __str__(self):
        return f"{self.__class__.__name__}:{self._config.device_identifier}"

    def start(self):
        super().start()

        # not supported platform, will raise exception during startup. no exception during init to not break the overall app
        assert input_ffmpeg_device is not None, "the platform is not supported"

    def stop(self):
        super().stop()

    def _device_name_platform(self):
        return f"video={self._config.device_identifier}" if sys.platform == "win32" else f"{self._config.device_identifier}"

    def _handle_switchmode_video_mode(self):
        super()._handle_switchmode_video_mode()

    def _handle_switchmode_still_mode(self):
        super()._handle_switchmode_still_mode()

    def _handle_switchmode_standby(self):
        super()._handle_switchmode_standby()

    def setup_resource(self):
        pass

    def teardown_resource(self):
        pass

    def run_service(self):
        reformatter = VideoReformatter()
        options = {
            "video_size": f"{self._config.cam_resolution_width}x{self._config.cam_resolution_height}",
            "input_format": "mjpeg",  # or h264 if supported is also possible but seems it has no effect (tested on windows dshow only)
            # "input_format": "yuyv422",
        }
        if self._config.cam_framerate > 0:
            # avfoundation has ntsc as default. webcams refuse to work with that framerate, so allow to set it explicit
            # dshow/v4l usually dont need this configured because their default seems reasonable.
            options["framerate"] = str(self._config.cam_framerate)

        rW = self._config.cam_resolution_width // self._config.preview_resolution_reduce_factor
        rH = self._config.cam_resolution_height // self._config.preview_resolution_reduce_factor

        while not self._stop_event.is_set():
            self._mode_machine.process_switchmode()

            if self._mode_machine.active_mode == "standby":
                time.sleep(0.1)
                continue

            try:
                logger.info(f"trying to open camera '{self._config.device_identifier}'")
                input_device = av.open(self._device_name_platform(), format=input_ffmpeg_device, options=options)
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
                logger.info(f"color_range: {ColorRange(input_stream.color_range).name} (Range JPEG=full, MPEG=limited)")
                logger.info(f"livestream resolution: {rW}x{rH}")

                try:
                    frame = next(input_device.demux(input_stream)).decode()[0]
                    logger.info(f"pyav frame received: {frame}")
                    logger.info(f"frame format: {frame.format}")
                    del frame
                except Exception as exc:
                    raise PermanentFault("Error decoding camera frame! Ensure the settings are correct (device name, fps, resolution, ...)") from exc

                codec_name = input_stream.codec.name

                for packet in input_device.demux(input_stream):
                    # for the rawvideo types and the mjpeg type, the camera packets consist of always 1 frame.
                    # the packet is the jpeg data to be received using bytes(packet) or the raw yuv data.
                    # in case we use mjpeg, we use the jpeg directly if possible. if we have rawvideo, we get the frame decoded
                    # using packet.decode() and process the frame pixel data

                    with self._hires_lock:
                        req = self._hires_queue.popleft() if self._hires_queue else None

                    # hires
                    if req:
                        if isinstance(req, StillRequest):
                            if codec_name == "mjpeg":
                                jpeg_bytes_hires = bytes(packet)
                            elif codec_name == "rawvideo":
                                frame = next(input_device.decode(input_stream))
                                image_bytesio = io.BytesIO()
                                frame.to_image().save(image_bytesio, format="JPEG", quality=90)
                                jpeg_bytes_hires = image_bytesio.getvalue()
                                del frame
                            else:
                                raise PermanentFault(f"The webcam's codec {codec_name} is not supported!")

                            # only capture one pic and return to lores streaming afterwards
                            with NamedTemporaryFile(
                                mode="wb",
                                delete=False,
                                dir="tmp",
                                prefix=f"{filename_str_time()}_pyav_",
                                suffix=".jpg",
                            ) as f:
                                f.write(jpeg_bytes_hires)

                            with req.condition:
                                req.result_file = Path(f.name)
                                req.condition.notify_all()

                            continue
                        else:
                            logger.warning(f"this backend does not support {type(req)} requests")
                            continue

                    # abort streaming on shutdown so process can join and close
                    if self._stop_event.is_set():
                        del packet  # del packet to allow buffer release in c ffmpeg python
                        break

                    self._mode_machine.process_switchmode()

                    if self._mode_machine.active_mode == "standby":
                        # no need to sleep here, because while loop is called on every frame only. otherwise pyav internal buffer runs full
                        # and floods logging
                        del packet  # del packet to allow buffer release in c ffmpeg python
                        break

                    if not self._framerate.should_process_frame(15):
                        continue

                    frame = next(input_device.decode(input_stream))

                    if self._config.preview_resolution_reduce_factor > 1:
                        out_frame = reformatter.reformat(
                            frame,
                            width=rW,
                            height=rH,
                            interpolation=Interpolation.BILINEAR,
                            format="yuv420p",
                            src_color_range=input_stream.color_range,
                            dst_color_range=ColorRange.JPEG,  # simplejpeg is full range
                        ).to_ndarray()
                    else:
                        out_frame = reformatter.reformat(
                            frame,
                            format="yuv420p",
                            src_color_range=input_stream.color_range,
                            dst_color_range=ColorRange.JPEG,  # simplejpeg is full range
                        ).to_ndarray()

                    # compress raw YUV420p to JPEG
                    jpeg_bytes = encode_jpeg_yuv_planes(
                        Y=out_frame[:rH],
                        U=out_frame.reshape(rH * 3, rW // 2)[rH * 2 : rH * 2 + rH // 2],
                        V=out_frame.reshape(rH * 3, rW // 2)[rH * 2 + rH // 2 :],
                        quality=85,
                        fastdct=True,
                    )
                    del out_frame, frame

                    with self._lores_data[0].condition:
                        self._lores_data[0].data = jpeg_bytes
                        self._lores_data[0].condition.notify_all()

                    self._frame_tick()

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
