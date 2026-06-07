"""
abstract for the photobooth-app backends
"""

import logging
import threading
import time
import uuid
from abc import ABC, abstractmethod
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from ...utils.resilientservice import ResilientService
from ..config.groups.cameras import Orientation
from .utils.rotate_exif import set_exif_orientation

logger = logging.getLogger(__name__)

Modes = Literal["still", "video", "standby"]


@dataclass
class BackendStats:
    """
    defines some common stats - if backend supports, they return these properties,
    if not, may be 0 or None
    """

    backend_name: str
    mode: str
    device_fps: int


@dataclass
class LoresBroadcastRes:
    # jpeg data as bytes
    data: bytes
    # condition when frame is avail
    condition: threading.Condition


@dataclass
class StillRequest:
    id: uuid.UUID
    subdevice_index: int
    result_file: Path | None = None
    error: Exception | None = None
    condition: threading.Condition = threading.Condition()


@dataclass
class MulticamRequest:
    id: uuid.UUID
    result_files: list[Path] | None = None
    error: Exception | None = None
    condition: threading.Condition = threading.Condition()


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
            # need at least 2 timestamps for fps calc
            if len(self._timestamps) < 2:
                return 0

            # invalidate outdated fps data after 1 sec of no frame received
            elapsed_since_last_add_frame = (time.monotonic_ns() - self._timestamps[-1]) * 1e-9
            if elapsed_since_last_add_frame > 1:
                self._timestamps.clear()

                return 0

            deltas = [self._timestamps[i] - self._timestamps[i - 1] for i in range(1, len(self._timestamps))]

        avg_delta_ns = sum(deltas) / len(deltas)
        return int(round(1.0 / (avg_delta_ns * 1e-9), 0))

    def _remaining_ns(self, target_fps: int) -> int:
        """
        Return remaining nanoseconds until the next frame should be processed.
        Positive → too early (should wait or skip)
        Zero/negative → OK to process now
        """
        if target_fps <= 0:
            return 0  # unlimited FPS

        target_delta_ns = int(1e9 / target_fps)

        with self._lock:
            if not self._timestamps:
                return 0  # no history → allow first frame
            last_ts = self._timestamps[-1]

        now = time.monotonic_ns()
        elapsed = now - last_ts
        return target_delta_ns - elapsed

    def wait_until_fps(self, target_fps: int) -> None:
        """public api, blocking"""
        remaining = self._remaining_ns(target_fps)
        if remaining > 0:
            time.sleep(remaining / 1e9)

    def should_process_frame(self, target_fps: int) -> bool:
        """public api, non-blocking"""
        # TODO: validate 0.5 tolerance.
        return self._remaining_ns(target_fps) <= int(0.5e9 / target_fps)


class ModeController:
    """
    Einfacher Mode-Controller mit:
    - requested_mode (Thread-agnostisch)
    - active_mode (nur im Stream-Thread gesetzt)
    - automatischem Standby nach Idle
    """

    def __init__(self, backend: "AbstractBackend", idle_timeout: float | None = None):
        self.backend = backend
        self.idle_timeout = idle_timeout

        self._lock = threading.Lock()
        self.requested_mode: Modes = "standby"
        self.active_mode: Modes | None = None
        self._last_live_request: float | None = time.monotonic()

        if self.idle_timeout:
            assert self.idle_timeout > 5, "The idle timeout to set the camera to standby needs to be disabled or at least 5s."

            threading.Thread(target=self._idle_monitor, daemon=True).start()

    # ---------------------------------------------------------
    # Öffentliche API (kann aus jedem Thread aufgerufen werden)
    # ---------------------------------------------------------

    def request_mode(self, mode: Modes):
        with self._lock:
            self.requested_mode = mode

    def request_video(self):
        """usually requested when creating a video but also for livestream. livestream request video on every frame to reset the timer.
        the stream thread needs to ensure a still capture is not interupted by another request to video!"""
        self.reset_standby_timer()  # on mode request always reset the timer, to avoid going to standby accidentally in race conditions
        self.request_mode("video")

    def request_still(self):
        self.reset_standby_timer()  # on mode request always reset the timer, to avoid going to standby accidentally in race conditions
        self.request_mode("still")

    def request_standby(self):
        self.request_mode("standby")

    def reset_standby_timer(self):
        with self._lock:
            self._last_live_request = time.monotonic()

    @property
    def is_mode_change_pending(self):
        with self._lock:
            return self.requested_mode != self.active_mode

    def _idle_monitor(self):
        """Monitor thread function to request standby if no livestream is requested for idle_timeout seconds"""
        assert self.idle_timeout

        logger.info(f"pausing livestream on backend {self.backend} after {self.idle_timeout}s is enabled.")

        while True:
            time.sleep(1)

            if self._last_live_request is None:
                continue

            with self._lock:
                idle = time.monotonic() - self._last_live_request
                act = self.active_mode

            if idle > self.idle_timeout and act == "video":
                logger.info(f"pause camera stream after {self.idle_timeout} idle timeout.")

                self._last_live_request = None

                self.request_standby()

    def process_switchmode(self, immediate_forced_mode: Modes | None = None):
        """Wird im stream-thread aufgerufen, wenn es passend für einen potentiellen mode-switch ist"""

        with self._lock:
            req = self.requested_mode if not immediate_forced_mode else immediate_forced_mode
            act = self.active_mode

        # Kein Modewechsel nötig
        if req == act:
            return

        logger.info(f"changing mode from {act} to {req} on backend {self.backend}")

        # Modewechsel durchführen
        if req == "video":
            self.backend._handle_switchmode_video_mode()
        elif req == "still":
            self.backend._handle_switchmode_still_mode()
        elif req == "standby":
            self.backend._handle_switchmode_standby()

        # Mode ist jetzt aktiv
        with self._lock:
            self.active_mode = req


class AbstractBackend(ResilientService, ABC):
    @abstractmethod
    def _handle_switchmode_standby(self):
        """called internally by supervising if liveview frames are requested"""

    @abstractmethod
    def _handle_switchmode_video_mode(self):
        """called externally via events and used to change to a preview mode if necessary"""

    @abstractmethod
    def _handle_switchmode_still_mode(self):
        """called externally via events and used to change to a capture mode if necessary"""

    @abstractmethod
    def __init__(self, orientation: Orientation, num_subdevices: int, idle_timeout: float | None):
        # init
        self._orientation: Orientation = orientation
        self._num_subdevices = num_subdevices
        self._idle_timeout = idle_timeout

        # statisitics attributes
        self._framerate: Framerate = Framerate()

        self._mode_machine = ModeController(self, idle_timeout=self._idle_timeout)

        # lores broadcast and ...
        self._lores_data = [LoresBroadcastRes(data=b"", condition=threading.Condition()) for _ in range(self._num_subdevices)]
        # ... hires queue
        self._hires_queue: deque[StillRequest | MulticamRequest] = deque(maxlen=1)
        self._hires_lock = threading.Lock()

        super().__init__()

    def __str__(self):
        return f"{self.__class__.__name__}"

    def __repr__(self):
        return f"{self.__class__.__name__}"

    def get_stats(self) -> BackendStats:
        stats = BackendStats(
            backend_name=self.__class__.__name__,
            mode=self._mode_machine.active_mode if self._mode_machine.active_mode else "unknown",
            device_fps=self._framerate.fps,
        )

        return stats

    def _frame_tick(self):
        """call by backends implementation when frame is delivered, so the fps can be calculated..."""
        self._framerate.add_frame()

    @abstractmethod
    def start(self):
        """To start the backend to serve"""

        super().start()

    @abstractmethod
    def stop(self):
        """To stop the backend to serve"""

        super().stop()

    def wait_for_multicam_files(self) -> list[Path]:
        if self._num_subdevices < 2:
            raise RuntimeError(f"cannot get multicam files as {self} has only {self._num_subdevices} subdevices but needs at least 2.")

        req = MulticamRequest(uuid.uuid4())

        self._mode_machine.request_still()

        with self._hires_lock:
            self._hires_queue.append(req)

        with req.condition:
            ok = req.condition.wait(timeout=8)

            if not ok:
                raise TimeoutError("timeout waiting for hires frame")
            if req.error:
                raise req.error

            filepaths = req.result_files
            assert filepaths

            for filepath in filepaths:
                set_exif_orientation(filepath, self._orientation)

            return filepaths

    def wait_for_still_file(self, index_subdevice: int = 0) -> Path:
        req = StillRequest(uuid.uuid4(), subdevice_index=index_subdevice)

        self._mode_machine.request_still()

        with self._hires_lock:
            self._hires_queue.append(req)

        with req.condition:
            ok = req.condition.wait(timeout=8)

            if not ok:
                raise TimeoutError("timeout waiting for hires frame")
            if req.error:
                raise req.error

            filepath = req.result_file
            assert filepath

            set_exif_orientation(filepath, self._orientation)

            return filepath

    def wait_for_lores_image(self, index_subdevice: int = 0) -> bytes:

        if index_subdevice > len(self._lores_data):
            raise RuntimeError(f"streaming from subdevice={index_subdevice} not possible because there are only {len(self._lores_data)} available.")

        self._mode_machine.request_video()

        with self._lores_data[index_subdevice].condition:
            if not self._lores_data[index_subdevice].condition.wait(timeout=2.0):
                raise TimeoutError("timeout receiving frames")

            img = self._lores_data[index_subdevice].data

            img = set_exif_orientation(img, self._orientation)

            return img

    @abstractmethod
    def setup_resource(self):
        pass

    @abstractmethod
    def teardown_resource(self):
        pass

    @abstractmethod
    def run_service(self):
        pass
