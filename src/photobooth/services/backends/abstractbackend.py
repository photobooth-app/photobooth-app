"""
abstract for the photobooth-app backends
"""

import logging
import threading
import time
from abc import ABC, abstractmethod
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from threading import Condition, Event

from ...utils.resilientservice import ResilientService
from ...utils.stoppablethread import StoppableThread
from ..config.groups.cameras import Orientation
from .utils.rotate_exif import set_exif_orientation

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
    """Thread-safe rolling-window FPS calculator."""

    _timestamps: deque[int] = field(default_factory=lambda: deque(maxlen=5))
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def add_frame(self) -> None:
        with self._lock:
            self._timestamps.append(time.monotonic_ns())

    @property
    def fps(self) -> int:
        with self._lock:
            if len(self._timestamps) < 2:
                return 0

            deltas = [self._timestamps[i] - self._timestamps[i - 1] for i in range(1, len(self._timestamps))]

        avg_delta_ns = sum(deltas) / len(deltas)
        return int(round(1.0 / (avg_delta_ns * 1e-9), 0))


class AbstractBackend(ResilientService, ABC):
    @abstractmethod
    def __init__(self, orientation: Orientation = "1: 0°", pause_camera_on_livestream_inactive: bool = False, timeout_until_inactive: int = 30):
        # init
        self._orientation: Orientation = orientation
        self._pause_camera_on_livestream_inactive: bool = pause_camera_on_livestream_inactive
        self._timeout_until_inactive: int = timeout_until_inactive

        # statisitics attributes
        self._backendstats: BackendStats = BackendStats(backend_name=self.__class__.__name__)
        self._framerate: Framerate = Framerate()

        # used to indicate if the app requires this backend to deliver actually lores frames (live-backend or only one main backend)
        # default is to assume it's not responsible to deliver frames. once wait_for_lores_image is called, this is set to true.
        # the backend-implementation has to decide how to handle this once True.
        self._last_requested_timestamp: float | None = None
        self._liveview_idle_thread: StoppableThread | None = None

        # data out (lores_data is locally handled per backend)
        self._hires_data: GeneralFileResult = GeneralFileResult(filepath=None, request=Event(), condition=Condition())

        super().__init__()

    def __str__(self):
        return f"{self.__class__.__name__}"

    def __repr__(self):
        return f"{self.__class__.__name__}"

    def get_stats(self) -> BackendStats:
        self._backendstats.fps = self._framerate.fps
        return self._backendstats

    def _frame_tick(self):
        """call by backends implementation when frame is delivered, so the fps can be calculated..."""
        self._framerate.add_frame()

    @property
    def livestream_requested(self) -> bool:
        return self._last_requested_timestamp is not None

    def _liveview_idle_fun(self):
        assert self._liveview_idle_thread
        logger.info("_liveview_idle_fun start")

        while not self._liveview_idle_thread.stopped():
            time.sleep(1)

            if self._last_requested_timestamp is None:
                continue

            inactive_seconds = time.monotonic() - self._last_requested_timestamp
            liveview_active = inactive_seconds < self._timeout_until_inactive

            if liveview_active is False:  # and flag_active_to_inactive_requested is False:
                # reset _last_requested_timestamp so this thread pauses processing
                # and indicate to backend to reconfigure.
                self._last_requested_timestamp = None
                logger.info(f"pause camera stream after {self._timeout_until_inactive} idle timeout.")

                self._on_configure_optimized_for_livestream_paused()

    @abstractmethod
    def start(self):
        """To start the backend to serve"""

        # reset the request for this backend to deliver lores frames
        self._last_requested_timestamp = None

        if self._pause_camera_on_livestream_inactive:
            logger.info(f"pausing livestream from camera after {self._timeout_until_inactive}s is enabled.")
            self._liveview_idle_thread = StoppableThread(name="_liveview_idle_fun", target=self._liveview_idle_fun, daemon=True)
            self._liveview_idle_thread.start()

        super().start()

    @abstractmethod
    def stop(self):
        """To stop the backend to serve"""

        if self._liveview_idle_thread:
            self._liveview_idle_thread.stop()
            self._liveview_idle_thread.join()

        super().stop()

    def wait_for_multicam_files(self, retries: int = 3) -> list[Path]:
        """
        function blocks until high quality image is available
        """

        attempt = 0
        while True:
            try:
                return self._wait_for_multicam_files()
            except NotImplementedError:
                # backend does not support, immediately reraise and done.
                raise
            except Exception as exc:
                attempt += 1

                if attempt <= retries:
                    logger.error(f"Error {exc} during capture. {attempt=}/{retries}")
                    continue
                else:
                    # we failed finally all the attempts - deal with the consequences.
                    raise RuntimeError(f"finally failed after {retries} attempts to capture image!") from exc

    def wait_for_still_file(self, retries: int = 3) -> Path:
        """
        function blocks until high quality image is available
        """
        attempt = 0
        while True:
            try:
                filepath = self._wait_for_still_file()
                set_exif_orientation(filepath, self._orientation)
                return filepath
            except Exception as exc:
                attempt += 1
                if attempt <= retries:
                    logger.error(f"Error {exc} during capture. {attempt=}/{retries}")
                    continue
                else:
                    # we failed finally all the attempts - deal with the consequences.
                    raise RuntimeError(f"finally failed after {retries} attempts to capture image!") from exc

    def pause_wait_for_lores_while_hires_capture(self):
        flag_logmsg_emitted_once = False
        while self._hires_data.request.is_set():
            if not flag_logmsg_emitted_once:
                logger.debug("pause_wait_for_lores_while_hires_capture until hires request is finished")
                flag_logmsg_emitted_once = True  # avoid flooding logs

            time.sleep(0.2)

    def wait_for_lores_image(self, retries: int = 10, index_subdevice: int = 0) -> bytes:
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

        for _ in range(retries):
            self._last_requested_timestamp = time.monotonic()

            try:
                img_bytes = self._wait_for_lores_image(index_subdevice=index_subdevice)  # blocks 0.5s usually. 10 retries default wait time=5s
                img = set_exif_orientation(img_bytes, self._orientation)
                return img
            except TimeoutError as exc:
                if self.is_started():
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
    def _wait_for_lores_image(self, index_subdevice: int = 0) -> bytes:
        """
        function blocks until frame is available for preview stream
        """

    @abstractmethod
    def _on_configure_optimized_for_livestream_paused(self):
        """called internally by supervising if liveview frames are requested"""

    @abstractmethod
    def _on_configure_optimized_for_idle(self):
        """called externally via events and used to change to a preview mode if necessary"""

    @abstractmethod
    def _on_configure_optimized_for_hq_preview(self):
        """called externally via events and used to change to a preview mode if necessary"""

    @abstractmethod
    def _on_configure_optimized_for_hq_capture(self):
        """called externally via events and used to change to a capture mode if necessary"""
