"""
abstract for the photobooth-app backends
"""

import io
import logging
import os
import subprocess
import threading
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from threading import Condition, Event

import piexif

from ... import LOG_PATH
from ...appconfig import appconfig
from ...utils.stoppablethread import StoppableThread
from ..config.groups.backends import Orientation
from .resilientservice import ResilientService

logger = logging.getLogger(__name__)


@dataclass
class BackendStats:
    """
    defines some common stats - if backend supports, they return these properties,
    if not, may be 0 or None
    """

    backend_name: str = __name__

    fps: int | None = None
    exposure_time_ms: float | None = None
    lens_position: float | None = None
    again: float | None = None
    dgain: float | None = None
    lux: float | None = None
    colour_temperature: int | None = None
    sharpness: int | None = None


@dataclass
class GeneralBytesResult:
    # jpeg data as bytes
    data: bytes
    # condition when frame is avail
    condition: threading.Condition


@dataclass
class GeneralFileResult:
    # jpeg data file for hires
    filepath: Path | None
    # signal to producer that requesting thread is ready to be notified
    request: threading.Event
    # condition when frame is avail
    condition: threading.Condition


@dataclass
class GeneralMultifileResult:
    # jpeg data file for hires
    filepath: list[Path] | None
    # signal to producer that requesting thread is ready to be notified
    request: threading.Event
    # condition when frame is avail
    condition: threading.Condition


@dataclass
class Framerate:
    """helps calculating the current framerate of backend.
    init empty and on every frame delivered, set current_timestamp with monotonic_ns() value
    when two timestamps are avail, the fps can be read from .fps

    Returns:
        int: Framerate
    """

    _last_timestamp: int | None = None
    _current_timestamp: int | None = None

    @property
    def current_timestamp(self) -> int | None:
        return self._current_timestamp

    @current_timestamp.setter
    def current_timestamp(self, v: int) -> None:
        self._last_timestamp = self._current_timestamp
        self._current_timestamp = v

    @property
    def fps(self) -> int:
        if self._last_timestamp and self._current_timestamp:
            return int(round(1.0 / ((self._current_timestamp - self._last_timestamp) * 1.0e-9), 0))
        else:
            return 0


class AbstractBackend(ResilientService, ABC):
    @abstractmethod
    def __init__(self, orientation: Orientation = "1: 0°"):
        # init
        self._orientation: Orientation = orientation

        # statisitics attributes
        self._backendstats: BackendStats = BackendStats(backend_name=self.__class__.__name__)
        self._framerate: Framerate = Framerate()

        # used to indicate if the app requires this backend to deliver actually lores frames (live-backend or only one main backend)
        # default is to assume it's not responsible to deliver frames. once wait_for_lores_image is called, this is set to true.
        # the backend-implementation has to decide how to handle this once True.
        self._device_enable_lores_flag: bool = False

        # video feature
        self._video_worker_capture_started: Event = Event()
        self._video_worker_thread: StoppableThread | None = None
        self._video_recorded_videofilepath: Path | None = None
        self._video_framerate: int | None = None

        # data out (lores_data is locally handled per backend)
        self._hires_data: GeneralFileResult = GeneralFileResult(filepath=None, request=Event(), condition=Condition())

        super().__init__()

    def __repr__(self):
        return f"{self.__class__}"

    def get_stats(self) -> BackendStats:
        self._backendstats.fps = self._framerate.fps
        return self._backendstats

    def _frame_tick(self):
        """call by backends implementation when frame is delivered, so the fps can be calculated..."""
        self._framerate.current_timestamp = time.monotonic_ns()

    @abstractmethod
    def start(self):
        """To start the backend to serve"""
        logger.debug(f"{self.__module__} start called")

        # reset the request for this backend to deliver lores frames
        self._device_enable_lores_flag = False

        super().start()

    @abstractmethod
    def stop(self):
        """To stop the backend to serve"""
        logger.debug(f"{self.__module__} stop called")

        self.stop_recording()

        super().stop()

    def rotate_jpeg_file_by_exif_flag(self, filepath: Path, orientation_choice: Orientation):
        """inserts updated orientation flag in given filepath.
        ref https://sirv.com/help/articles/rotate-photos-to-be-upright/

        Args:
            filepath (Path): file to modify
            orientation_value (int): Orientierung (1=0°, 3=180°, 5=90°, 7=270°)
        """
        piexif.insert(self._get_updated_exif_bytes(str(filepath), orientation_choice), str(filepath))

    def rotate_jpeg_data_by_exif_flag(self, image_data: bytes, orientation_choice: Orientation):
        """reads exif from image_data bytes and returns new bytes with updated orientation.
        ref: https://sirv.com/help/articles/rotate-photos-to-be-upright/

        Args:
            image_data (bytes): data to modify
            orientation_value (int): Orientierung (0=0°, 3=180°, 5=90°, 7=270°)
        """
        output = io.BytesIO()
        piexif.insert(self._get_updated_exif_bytes(image_data, orientation_choice), image_data, output)

        return output.getvalue()

    def _get_updated_exif_bytes(self, maybe_image, orientation_choice: Orientation):
        assert isinstance(orientation_choice, str)

        orientation = int(orientation_choice[0])
        if 1 < orientation > 8:
            raise ValueError(f"invalid orientation choice {orientation_choice} results in invalid value: {orientation}.")

        exif_dict = piexif.load(maybe_image)
        exif_dict["0th"][piexif.ImageIFD.Orientation] = orientation

        return piexif.dump(exif_dict)

    def wait_for_multicam_files(self, retries: int = 3) -> list[Path]:
        """
        function blocks until high quality image is available
        """

        for attempt in range(1, retries + 1):
            try:
                return self._wait_for_multicam_files()
            except NotImplementedError:
                # backend does not support, immediately reraise and done.
                raise
            except Exception as exc:
                logger.exception(exc)
                logger.error(f"error capture image. {attempt=}/{retries}, retrying")
                continue

        else:
            # we failed finally all the attempts - deal with the consequences.
            logger.critical(f"finally failed after {retries} attempts to capture image!")

            raise RuntimeError(f"finally failed after {retries} attempts to capture image!")

    def wait_for_still_file(self, retries: int = 3) -> Path:
        """
        function blocks until high quality image is available
        """
        attempt = 0
        while True:
            try:
                filepath = self._wait_for_still_file()
                self.rotate_jpeg_file_by_exif_flag(filepath, self._orientation)
                return filepath
            except Exception as exc:
                attempt += 1
                if attempt <= retries:
                    logger.warning(f"capture image in {attempt=}/{retries}. retrying.")
                    continue
                else:
                    # we failed finally all the attempts - deal with the consequences.
                    logger.exception(exc)
                    raise RuntimeError(f"finally failed after {retries} attempts to capture image!") from exc

    def pause_wait_for_lores_while_hires_capture(self):
        flag_logmsg_emitted_once = False
        while self._hires_data.request.is_set():
            if not flag_logmsg_emitted_once:
                logger.debug("pause_wait_for_lores_while_hires_capture until hires request is finished")
                flag_logmsg_emitted_once = True  # avoid flooding logs

            time.sleep(0.2)

    def wait_for_lores_image(self, retries: int = 10) -> bytes:
        """Function called externally to receivea low resolution image.
        Also used to stream. Tries to recover up to retries times before giving up.

        Args:
            retries (int, optional): How often retry to use the private _wait_for_lores_image function before failing. Defaults to 10.

        Raises:
            exc: Shutdown is handled different, no retry
            exc: All other exceptions will lead to retry before finally fail.

        Returns:
            _type_: _description_
        """
        self._device_enable_lores_flag = True

        for _ in range(retries):
            try:
                img_bytes = self._wait_for_lores_image()  # blocks 0.5s usually. 10 retries default wait time=5s
                img = self.rotate_jpeg_data_by_exif_flag(img_bytes, self._orientation)
                return img
            except TimeoutError as exc:
                if self.is_running():
                    continue
                else:
                    logger.debug("device not alive any more, stopping early lores image delivery.")
                    raise StopIteration from exc
            except Exception as exc:
                # other exceptions fail immediately
                logger.warning("device raised exception (maybe lost connection to device?)")
                raise exc

        # max attempts reached.
        raise RuntimeError(f"failed getting images after {retries} attempts.")

    def start_recording(self, video_framerate: int) -> Path:
        self._video_worker_capture_started.clear()
        self._video_framerate = video_framerate

        # generate temp filename to record to
        mp4_output_filepath = Path("tmp", f"{self.__class__.__name__}_{uuid.uuid4().hex}").with_suffix(".mp4")

        self._video_worker_thread = StoppableThread(name="_videoworker_fun", target=self._videoworker_fun, args=(mp4_output_filepath,), daemon=True)
        self._video_worker_thread.start()

        tms = time.time()
        # gives 3 seconds to actually capture with ffmpeg, otherwise timeout. if ffmpeg is not in memory it needs time to load from disk
        if not self._video_worker_capture_started.wait(timeout=3):
            logger.warning("ffmpeg could not start within timeout; cpu too slow?")
        logger.debug(f"-- ffmpeg startuptime: {round((time.time() - tms), 2)}s ")

        return mp4_output_filepath

    def is_recording(self):
        return self._video_worker_thread is not None and self._video_worker_capture_started.is_set()

    def stop_recording(self):
        # clear notifier that capture was started
        self._video_worker_capture_started.clear()

        if self._video_worker_thread:
            logger.debug("stop recording")
            self._video_worker_thread.stop()
            self._video_worker_thread.join()
            logger.info("_video_worker_thread stopped and joined")

        else:
            logger.info("no _video_worker_thread active that could be stopped")

    def _videoworker_fun(self, mp4_output_filepath: Path):
        logger.info("_videoworker_fun start")
        # init worker, set output to None which indicates there is no current video available to get
        self._video_recorded_videofilepath = None

        command_general_options = [
            "-hide_banner",
            "-loglevel",
            "info",
            "-y",
        ]
        command_video_input = [
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
        ]
        command_video_output = [
            "-vcodec",
            "libx264",  # warning! image height must be divisible by 2! #there are also hw encoder avail: https://stackoverflow.com/questions/50693934/different-h264-encoders-in-ffmpeg
            "-preset",
            "veryfast",
            "-b:v",
            f"{appconfig.mediaprocessing.video_bitrate}k",
            "-movflags",
            "+faststart",
            "-r",
            f"{self._video_framerate}",
        ]
        command_video_output_compat_mode = []
        if appconfig.mediaprocessing.video_compatibility_mode:
            # fixes #233. needs more cpu and seems deprecated, maybe in future it will be configurable to disable
            command_video_output_compat_mode = [
                "-pix_fmt",
                "yuv420p",
            ]

        ffmpeg_command = (
            ["ffmpeg"]
            + command_general_options
            + command_video_input
            + command_video_output
            + command_video_output_compat_mode
            + [str(mp4_output_filepath)]
        )

        try:
            ffmpeg_subprocess = subprocess.Popen(
                ffmpeg_command,
                stdin=subprocess.PIPE,
                # following report is workaround to avoid deadlock by pushing too much output in stdout/err
                # https://thraxil.org/users/anders/posts/2008/03/13/Subprocess-Hanging-PIPE-is-your-enemy/
                env=dict(os.environ, FFREPORT=f"file={LOG_PATH}/ffmpeg-last.log:level=32"),
                # stdout=subprocess.PIPE,
                # stderr=subprocess.STDOUT,
            )
            assert ffmpeg_subprocess.stdin
        except Exception as exc:
            logger.error(f"starting ffmpeg failed: {exc}")
            return

        logger.info("writing to ffmpeg stdin")
        tms = time.time()

        # inform calling function, that ffmpeg received first image now
        self._video_worker_capture_started.set()

        assert self._video_worker_thread
        while not self._video_worker_thread.stopped():
            try:
                # retry with a low number because video would be messed anyways if needs to retry
                ffmpeg_subprocess.stdin.write(self.wait_for_lores_image(retries=4))
                ffmpeg_subprocess.stdin.flush()  # forces every frame to get timestamped individually
            except Exception as exc:  # presumably a BrokenPipeError? should we check explicitly?
                ffmpeg_subprocess = None
                logger.exception(exc)
                logger.error(f"Failed to create video! Error: {exc}")

                self._video_worker_thread.stop()
                break

        if ffmpeg_subprocess is not None:
            logger.info("writing to ffmpeg stdin finished")
            logger.debug(f"-- process time: {round((time.time() - tms), 2)}s ")

            # release final video processing
            tms = time.time()

            _, ffmpeg_stderr = ffmpeg_subprocess.communicate()  # send empty to stdin, indicates close and gets stderr/stdout; shut down tidily
            code = ffmpeg_subprocess.wait()  # Give it a moment to flush out video frames, but after that make sure we terminate it.

            if code != 0:
                logger.error(ffmpeg_stderr)  # can help to track down errors for non-zero exitcodes.

                logger.error(f"error creating videofile, ffmpeg exit code ({code}).")
                # note: there is more information in ffmpeg logfile: ffmpeg-last.log

            ffmpeg_subprocess = None

            logger.info("ffmpeg finished")
            logger.debug(f"-- process time: {round((time.time() - tms), 2)}s ")

            logger.info(f"record written to {mp4_output_filepath}")

        logger.info("leaving _videoworker_fun")

    #
    # ABSTRACT METHODS TO BE IMPLEMENTED BY CONCRETE BACKEND (cv2, v4l, ...)
    #

    @abstractmethod
    def _wait_for_multicam_files(self) -> list[Path]:
        """
        function blocks until image still is available
        """

    @abstractmethod
    def _wait_for_still_file(self) -> Path:
        """
        function blocks until image still is available
        """

    @abstractmethod
    def _wait_for_lores_image(self) -> bytes:
        """
        function blocks until frame is available for preview stream
        """

    @abstractmethod
    def _on_configure_optimized_for_idle(self):
        """called externally via events and used to change to a preview mode if necessary"""

    @abstractmethod
    def _on_configure_optimized_for_hq_preview(self):
        """called externally via events and used to change to a preview mode if necessary"""

    @abstractmethod
    def _on_configure_optimized_for_hq_capture(self):
        """called externally via events and used to change to a capture mode if necessary"""
