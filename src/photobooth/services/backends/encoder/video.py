import io
import logging
import time
from fractions import Fraction
from pathlib import Path
from threading import Lock

import av
from PIL import Image

from ....appconfig import appconfig
from ....utils.helper import filename_str_time
from ....utils.stoppablethread import StoppableThread
from ..abstractbackend import AbstractBackend

logger = logging.getLogger(__name__)


class SoftwareVideoRecorder:
    """
    A standalone video recorder that:
    - runs in its own thread
    - pulls lores frames from the backend
    - writes them to ffmpeg
    - is controlled externally
    """

    def __init__(self, backend: AbstractBackend):
        self._backend = backend

        self._thread: StoppableThread | None = None
        self._output_filepath: Path | None = None
        self._lock = Lock()

    def start_recording(self, video_framerate: int, subdevice_index: int = 0) -> Path:
        """
        Start recording. Returns the output filepath.
        """
        with self._lock:
            if self.is_recording():
                raise RuntimeError("cannot start two records at the same time!")

            self._output_filepath = Path("tmp", f"{filename_str_time()}_{self._backend.__class__.__name__}_video").with_suffix(".mp4")

            self._thread = StoppableThread(name="SoftVideoRec", target=self._thread_fun, args=(video_framerate, subdevice_index), daemon=True)
            self._thread.start()

        return self._output_filepath

    def stop_recording(self):
        with self._lock:
            if self._thread:
                self._thread.stop()
                self._thread.join()
                self._thread = None

    def is_recording(self) -> bool:
        return self._thread is not None

    def _thread_fun(self, video_framerate: int, subdevice_index: int):
        assert self._thread

        logger.info("SoftwareVideoRecorder: start")

        frame_bytes = self._backend.wait_for_lores_image(subdevice_index)
        pil_img = Image.open(io.BytesIO(frame_bytes))
        width, height = pil_img.size

        with av.open(self._output_filepath, mode="w") as container:
            stream = container.add_stream("h264", rate=video_framerate, options={})
            stream.width = width
            stream.height = height
            stream.time_base = Fraction(1, video_framerate)
            stream.codec_context.options["movflags"] = "faststart"
            stream.codec_context.options["preset"] = "veryfast"
            stream.codec_context.thread_type = "AUTO"
            stream.codec_context.thread_count = 0  # let FFmpeg decide
            # stream.codec_context.profile = "Main"

            if appconfig.mediaprocessing.video_compatibility_mode:
                stream.pix_fmt = "yuv420p"

            stream.codec_context.bit_rate = appconfig.mediaprocessing.video_bitrate * 1000

            # This is the key: ffmpeg -use_wallclock_as_timestamps
            start_wallclock = time.monotonic()

            while not self._thread.stopped():
                frame_bytes = self._backend.wait_for_lores_image(subdevice_index)
                pil_img = Image.open(io.BytesIO(frame_bytes))
                video_frame: av.VideoFrame = av.VideoFrame.from_image(pil_img)
                # Compute wallclock timestamp
                now = time.monotonic()
                pts_seconds = now - start_wallclock
                video_frame.time_base = stream.time_base
                video_frame.pts = int(pts_seconds / float(stream.time_base))

                for packet in stream.encode(video_frame):
                    container.mux(packet)

            # Flush stream
            for packet in stream.encode():
                container.mux(packet)

            # Close the file
            # container.close()

        logger.info("SoftwareVideoRecorder: finished")
