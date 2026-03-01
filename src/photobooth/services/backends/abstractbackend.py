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

from statemachine import State, StateMachine

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
            if len(self._timestamps) < 2:
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
        return self._remaining_ns(target_fps) <= 0


class ModeMachine(StateMachine):
    standby = State(initial=True)
    video_mode = State()
    still_mode = State()

    pause = standby.to.itself(internal=True) | standby.from_(video_mode, still_mode)
    ensure_still_mode = still_mode.to.itself(internal=True) | still_mode.from_(standby, video_mode)
    ensure_video_mode = video_mode.to.itself(internal=True) | video_mode.from_(standby, still_mode)

    live_requested_ext = video_mode.to.itself(internal=True) | video_mode.from_(standby)

    thrill_video_ext = video_mode.to.itself(internal=True) | video_mode.from_(standby, still_mode)
    thrill_still_ext = still_mode.to.itself(internal=True) | still_mode.from_(standby, video_mode)

    def __init__(self, backend: "AbstractBackend"):
        self._backend = backend
        self._mode_switch_lock = threading.Lock()

        super().__init__()

    def on_enter_standby(self):
        with self._mode_switch_lock:
            print("switchmode_standby")
            self._backend._handle_switchmode_standby()

    def on_enter_video_mode(self):
        with self._mode_switch_lock:
            print("on_enter_video_mode")
            self._backend._handle_switchmode_video_mode()

    def on_enter_still_mode(self):
        with self._mode_switch_lock:
            print("on_enter_still_mode")
            self._backend._handle_switchmode_still_mode()

    def on_live_requested_ext(self):
        self._backend._last_requested_timestamp = time.monotonic()


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
    def __init__(self, orientation: Orientation, num_subdevices: int):
        # init
        self._orientation: Orientation = orientation
        self._num_subdevices = num_subdevices
        self._timeout_until_inactive: int = 30  # TODO: configurables

        # statisitics attributes
        self._framerate: Framerate = Framerate()

        # used to indicate if the app requires this backend to deliver actually lores frames (live-backend or only one main backend)
        # default is to assume it's not responsible to deliver frames. once wait_for_lores_image is called, this is set to true.
        # the backend-implementation has to decide how to handle this once True.
        self._last_requested_timestamp: float | None = None
        self._liveview_idle_thread: StoppableThread | None = None  # TODO: needs separate thread?

        self._mode_machine = ModeMachine(self)

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
            mode=next(iter(self._mode_machine.configuration)).name,  # new in state-machine v3, could have parallel states, we use flat machine
            device_fps=self._framerate.fps,
        )

        return stats

    def _frame_tick(self):
        """call by backends implementation when frame is delivered, so the fps can be calculated..."""
        self._framerate.add_frame()

    def _liveview_idle_fun(self):
        assert self._liveview_idle_thread
        logger.info(f"pausing livestream from camera after {self._timeout_until_inactive}s is enabled.")

        while not self._liveview_idle_thread.stopped():
            time.sleep(1)

            if self._last_requested_timestamp is None:
                continue

            if self._mode_machine.video_mode.is_active:  # type: ignore
                if (time.monotonic() - self._last_requested_timestamp) > self._timeout_until_inactive:
                    logger.info(f"pause camera stream after {self._timeout_until_inactive} idle timeout.")

                    self._last_requested_timestamp = None

                    self._mode_machine.pause()

    @abstractmethod
    def start(self):
        """To start the backend to serve"""

        # reset the request for this backend to deliver lores frames
        self._last_requested_timestamp = None

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

    def wait_for_multicam_files(self) -> list[Path]:
        if self._num_subdevices < 2:
            raise RuntimeError(f"cannot get multicam files as {self} has only {self._num_subdevices} subdevices but needs at least 2.")

        req = MulticamRequest(uuid.uuid4())

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

        self._mode_machine.live_requested_ext()  # since python-sm v3 allow_event_without_transition is True, so no check if allowed, just request

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
