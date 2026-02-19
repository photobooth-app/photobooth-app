import logging
import os
import subprocess
import threading
from pathlib import Path

from .... import LOG_PATH
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
        self._capture_started = threading.Event()
        self._output_filepath: Path | None = None

    def start_recording(self, video_framerate: int) -> Path:
        """
        Start recording. Returns the output filepath.
        """
        if self.is_recording():
            raise RuntimeError("cannot start two records at the same time!")

        self._capture_started.clear()

        self._output_filepath = Path("tmp", f"{filename_str_time()}_{self._backend.__class__.__name__}_video").with_suffix(".mp4")

        self._thread = StoppableThread(name="SoftwareVideoRecorder", target=self._thread_fun, args=(video_framerate,), daemon=True)
        self._thread.start()

        # wait for ffmpeg to start
        if not self._capture_started.wait(timeout=3):
            logger.warning("ffmpeg did not start within timeout")

        return self._output_filepath

    def stop_recording(self):
        if self._thread:
            self._thread.stop()
            self._thread.join()
            self._thread = None

    def is_recording(self) -> bool:
        return self._thread is not None and self._capture_started.is_set()

    def _thread_fun(self, video_framerate: int):
        assert self._thread

        logger.info("SoftwareVideoRecorder: start")

        ffmpeg_cmd = [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "info",
            "-y",
            "-use_wallclock_as_timestamps",
            "1",
            "-thread_queue_size",
            "64",
            "-f",
            "image2pipe",
            "-vcodec",
            "mjpeg",
            "-i",
            "-",
            "-vcodec",
            "libx264",
            "-preset",
            "veryfast",
            "-b:v",
            f"{appconfig.mediaprocessing.video_bitrate}k",
            "-movflags",
            "+faststart",
            "-r",
            f"{video_framerate}",
        ]

        if appconfig.mediaprocessing.video_compatibility_mode:
            ffmpeg_cmd += ["-pix_fmt", "yuv420p"]

        ffmpeg_cmd.append(str(self._output_filepath))

        try:
            proc = subprocess.Popen(
                ffmpeg_cmd,
                stdin=subprocess.PIPE,
                env=dict(os.environ, FFREPORT=f"file={LOG_PATH}/ffmpeg-last.log:level=32"),
            )
            assert proc.stdin
        except Exception as exc:
            logger.error(f"Failed to start ffmpeg: {exc}")
            return

        self._capture_started.set()

        while not self._thread.stopped():
            try:
                frame = self._backend.wait_for_lores_image(retries=4)
                proc.stdin.write(frame)
                proc.stdin.flush()
            except Exception as exc:
                logger.error(f"Video recording failed: {exc}")
                break

        # finalize ffmpeg
        try:
            proc.stdin.close()
            proc.wait(timeout=5)
        except Exception:
            proc.kill()

        logger.info("SoftwareVideoRecorder: finished")
