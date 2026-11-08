"""Olympus wifi backend for photobooth.

Drives a wifi-enabled Olympus camera through the ``olympuswifi`` library
(https://olympus-wifi.readthedocs.io). The camera acts as its own wifi access
point and normally exposes its control interface at 192.168.0.10; the
``device_ip`` config value lets this backend override that address.

How it works:
    - liveview (``wait_for_lores_image``): the camera streams MJPEG over
      RTP/UDP to a local port; ``LiveViewReceiver`` reassembles full JPEG
      frames and the worker loop broadcasts them to ``_lores_data``.
    - still (``wait_for_still_file``): olympuswifi's ``take_picture`` fires the
      shutter, we poll ``list_images`` for the newest file, download it with
      ``download_image`` and hand the resulting JPEG to the request.

The backend follows the same contract as every other backend: it runs inside
``ResilientService`` (setup -> run_service -> teardown) and serves requests via
the hires queue / lores broadcast mechanisms of ``AbstractBackend``.
"""

import logging
import queue
import re
import threading
import time
from pathlib import Path
from tempfile import NamedTemporaryFile

from olympuswifi.camera import OlympusCamera
from olympuswifi.liveview import LiveViewReceiver

from ...utils.helper import filename_str_time
from ..config.groups.cameras import GroupCameraOlympus
from .abstractbackend import AbstractBackend, StillRequest

logger = logging.getLogger(__name__)


class SupersededError(RuntimeError):
    """A camera call whose session (reconnect/teardown) ended before it ran."""


class _CameraCallPool:
    """Run camera HTTP calls on a small BOUNDED pool of daemon threads.

    ``olympuswifi`` issues ``requests`` without a transport timeout, so a call
    against an unreachable camera can block without bound. ``run_bounded``
    formerly spawned a fresh daemon thread per call: an unresponsive camera left
    blocked threads accumulating on every retry, and a late state-changing
    command could act on a replacement session after a reconnect/teardown.

    This pool fixes both without patching the library (its requests calls carry
    no timeout and use no injectable session):
      * a fixed number of daemon workers (default 4) bounds thread growth, so a
        stuck camera can never accumulate unbounded threads, and none of them
        (daemon) blocks process exit;
      * a bounded queue stops runaway submission;
      * a generation token is captured at submit time; a worker drops any call
        whose generation no longer matches the current one, so a command queued
        before a reconnect/teardown never reaches the camera of a newer session.
    """

    def __init__(self, max_workers: int = 4):
        self._q: queue.Queue[dict] = queue.Queue(maxsize=64)
        self._gen = 0
        self._lock = threading.Lock()
        self._workers: list[threading.Thread] = []
        for i in range(max_workers):
            t = threading.Thread(target=self._run, daemon=True, name=f"OlympusCamCall-{i}")
            t.start()
            self._workers.append(t)

    def _current_gen(self) -> int:
        with self._lock:
            return self._gen

    def invalidate(self) -> None:
        """Mark every not-yet-started call as superseded.

        Dequeued/running calls cannot be aborted (no transport timeout), but
        their callers already bound their own wait, and any call still queued
        for the old session is dropped on dequeue so it cannot act on a
        replacement session.
        """
        with self._lock:
            self._gen += 1

    def _run(self) -> None:
        while True:
            box = self._q.get()
            if box["generation"] != self._current_gen():
                # session ended before this command started: never touch the
                # camera (it may belong to a newer session by now)
                box["error"] = SupersededError("camera session changed")
                box["done"].set()
                continue
            try:
                box["value"] = box["fn"](*box["args"], **box["kwargs"])
            except BaseException as exc:  # noqa: BLE001 propagate whatever failed
                box["error"] = exc
            box["done"].set()

    def submit(self, fn, args, kwargs, timeout: float, desc: str):
        box = {
            "generation": self._current_gen(),
            "fn": fn,
            "args": args,
            "kwargs": kwargs,
            "done": threading.Event(),
            "value": None,
            "error": None,
        }
        try:
            self._q.put(box, timeout=1.0)
        except queue.Full as exc:
            raise TimeoutError(f"Olympus {desc}: camera call queue full (camera unresponsive?)") from exc
        if not box["done"].wait(timeout):
            raise TimeoutError(f"Olympus {desc} timed out after {timeout}s (camera unreachable?)")
        if box["error"] is not None:
            raise box["error"]
        return box["value"]


_POOL: _CameraCallPool | None = None
_POOL_LOCK = threading.Lock()


def _pool() -> _CameraCallPool:
    global _POOL
    with _POOL_LOCK:
        if _POOL is None:
            _POOL = _CameraCallPool()
        return _POOL


def invalidate_camera_calls() -> None:
    """Invalidate pending camera calls because the session is changing.

    Called on teardown and whenever the connection is dropped/replaced, so
    stale queued commands cannot act on a newer camera session.
    """
    _pool().invalidate()


def run_bounded(fn, *args, timeout: float = 3.0, desc: str = "camera command", **kwargs):
    """Run a camera call with a hard time cap.

    ``olympuswifi`` issues HTTP requests without a timeout, so a call against an
    unreachable camera could block the worker (and therefore shutdown, whose
    ``ResilientService`` join is bounded) for a very long time. The call runs on
    a bounded pool of daemon threads (no unbounded thread accumulation) and the
    caller gives up after ``timeout`` seconds, raising ``TimeoutError``. On a real
    exception inside the call it is re-raised; a call dropped because the camera
    session changed raises ``SupersededError``.
    """
    return _pool().submit(fn, args, kwargs, timeout, desc)


# Default well-known address of an Olympus wifi camera.
DEFAULT_CAMERA_WIFI_IP = "192.168.0.10"


def create_olympus_camera(ip: str) -> OlympusCamera:
    """Build an ``OlympusCamera`` bound to the given wifi address.

    ``olympuswifi`` hardcodes the camera address in the class attributes
    ``URL_PREFIX`` and ``HEADERS['Host']`` and contacts it from the constructor,
    so we override those attributes on a small subclass *before* instantiation.
    This keeps ``device_ip`` meaningful while leaving the library class untouched.
    """
    ip = (ip or DEFAULT_CAMERA_WIFI_IP).strip()
    base = OlympusCamera

    class ConfigurableOlympusCamera(base):
        URL_PREFIX = f"http://{ip}/"
        HEADERS = {**base.HEADERS, "Host": ip}

    return ConfigurableOlympusCamera()


def select_liveview_quality(camera: OlympusCamera) -> str:
    """Return the highest liveview resolution the camera advertises.

    The supported resolutions are published in the description of the
    ``switch_cammode`` command. Falls back to the library default
    (``0640x0480``) when the list cannot be read.
    """
    try:
        switch_cammode = camera.get_commands().get("switch_cammode")
        args = switch_cammode.args if switch_cammode else None
        mode = args.get("mode") if args else None
        rec = mode.get("rec") if mode else None
        lvqty = rec.get("lvqty") if rec else None
        resolutions = [option for option in (lvqty or {}) if isinstance(option, str) and re.fullmatch(r"\d+x\d+", option)]
        if resolutions:
            return max(resolutions, key=lambda res: _pixels(res))
    except (AttributeError, KeyError, TypeError):
        pass
    return OlympusCamera.DEFAULT_RES


def _pixels(resolution: str) -> int:
    width, _, height = resolution.partition("x")
    try:
        return int(width) * int(height)
    except ValueError:
        return 0


def make_placeholder_jpeg() -> bytes | None:
    """Return a small solid \"busy\" JPEG to serve during a still capture.

    Served to the lores stream so the frontend websocket stays fed (no retry
    timeouts) without showing a live picture while a photo is being taken and
    its photo is being displayed. ``None`` when Pillow is unavailable: the
    backend then simply serves no frames during the capture. Best-effort.
    """
    try:
        from io import BytesIO

        from PIL import Image, ImageDraw

        img = Image.new("RGB", (640, 480), (18, 22, 28))
        draw = ImageDraw.Draw(img)
        draw.text((16, 8), "Olympus - photo in progress...", fill=(180, 190, 200))
        buffer = BytesIO()
        img.save(buffer, "JPEG", quality=70)
        return buffer.getvalue()
    except Exception as exc:  # noqa: BLE001 - placeholder is best-effort
        logger.debug(f"Olympus: could not build placeholder frame: {exc}")
        return None


class OlympusBackend(AbstractBackend):
    """Backend for wifi-enabled Olympus cameras via the ``olympuswifi`` library."""

    # If the camera stops sending RTP for this long while liveview is active
    # (power cycle, lost liveview subscription, camera busy), the stream is
    # declared stalled and liveview is resubscribed instead of treating every
    # empty read as normal forever. Generous enough to never false-positive on a
    # brief hiccup (healthy stream is ~15fps, reads are 0.2s).
    LIVEVIEW_STALL_TIMEOUT: float = 5.0

    def __init__(self, config: GroupCameraOlympus):
        super().__init__(
            orientation=config.orientation,
            num_subdevices=1,
            idle_timeout=(config.camera_standby_when_inactive_time if config.camera_standby_when_inactive else None),
        )
        self._config = config

        self._camera: OlympusCamera | None = None
        self._receiver: LiveViewReceiver | None = None
        self._receiver_thread: threading.Thread | None = None
        # True when teardown had to retain a liveview receiver still holding the
        # UDP port; the next session must reap (join) it before re-binding,
        # instead of blindly reusing a socket it cannot get.
        self._receiver_orphaned: bool = False
        self._frame_queue: queue.SimpleQueue = queue.SimpleQueue()
        # liveview resolution, read lazily from the camera on first connect
        self._lvqty: str | None = None
        # whether a liveview is currently streaming from the camera
        self._liveview_active: bool = False
        # post-capture settle: the backend stays out of liveview for a short
        # beat after a still, so the after-screen is not flooded with frames.
        self._settle_after_capture: float = config.camera_settle_after_capture
        # Liveview freeze: while a still is downloading, and for a short
        # "display" beat after it, the backend serves a static placeholder to
        # the lores stream instead of live frames. This keeps the frontend
        # websocket fed (no retry timeouts) while showing only the photo, and
        # stops the livestream from jumping back in before the capture ends.
        self._capture_in_progress: bool = False
        self._capture_thread: threading.Thread | None = None
        # Generation token: bumped each time a capture starts or teardown runs.
        # An in-flight capture worker compares its own token against this one
        # and stops the moment it is superseded (new capture / shutdown), so it
        # never delivers a stale result or mutates shared state of a new session.
        self._capture_generation: int = 0
        self._freeze_until: float = 0.0
        self._placeholder: bytes | None = None
        # consecutive failed liveview (re)starts, used to back off the retry
        # loop so a camera that is busy after a capture does not sit in a tight
        # reconnect churn (the "stuck / no stream" pit state).
        self._liveview_start_failures: int = 0
        # last time a liveview frame was received (monotonic); a sustained gap
        # here while liveview is active means the camera stopped broadcasting.
        self._last_frame_time: float = 0.0

    # ------------------------------------------------------------------
    # Lifecycle hooks (delegated to the base classes)
    # ------------------------------------------------------------------
    def start(self):
        super().start()

    def stop(self):
        super().stop()

    # ------------------------------------------------------------------
    # Mode transitions (called by the ModeController)
    # ------------------------------------------------------------------
    def _handle_switchmode_init(self):
        logger.debug("Olympus: device init")

    def _handle_switchmode_video_mode(self):
        self._start_liveview()

    def _handle_switchmode_still_mode(self):
        # Nothing to change on the camera side: olympuswifi.take_picture()
        # handles the record/shutter transitions internally, and several models
        # need the liveview to be running in order to fire the shutter.
        logger.debug("Olympus: still mode (liveview kept active)")

    def _handle_switchmode_standby(self):
        self._stop_liveview()

    # ------------------------------------------------------------------
    # Connection
    # ------------------------------------------------------------------
    def _connect(self) -> bool:
        """Return ``True`` when a camera answers over wifi."""
        if self._camera is not None:
            return True

        ip = self._config.device_ip or DEFAULT_CAMERA_WIFI_IP
        try:
            # The OlympusCamera constructor itself performs an unbounded HTTP
            # request (get_commandlist). It must be capped too, otherwise a
            # reconnect attempt at shutdown blocks the worker and hangs stop().
            camera = run_bounded(
                create_olympus_camera,
                ip,
                timeout=5.0,
                desc="connect/get_commandlist",
            )
            if camera is None:
                raise RuntimeError("Olympus: connect returned no camera object.")
            info = camera.get_camera_info()
            if not info or "model" not in info:
                logger.warning(f"Olympus camera did not answer on {ip}.")
                return False

            self._camera = camera
            self._lvqty = select_liveview_quality(camera)
            self._liveview_active = False  # fresh camera object -> fresh state
            logger.info(f"Connected to Olympus {info.get('model')} on {ip}.")
            return True
        except Exception as exc:
            logger.warning(f"Olympus camera not reachable ({ip}): {exc}")
            invalidate_camera_calls()
            self._camera = None
            return False

    # ------------------------------------------------------------------
    # Liveview
    # ------------------------------------------------------------------
    def _ensure_receiver(self) -> None:
        """Make sure the UDP liveview receiver thread is running.

        ``receive_packets(port)`` binds the socket, hence the explicit port.
        Self-healing: if the thread died (socket error), this recreates it so
        the stream resumes without a full backend restart.
        """
        if self._receiver_orphaned:
            # A prior session's listener that teardown could not fully stop
            # still owns the UDP port. It was shut down (running=False) so it
            # exits on its next recv timeout, but we must not bind a new socket
            # until it is gone - join it (bounded) before re-binding.
            stale = self._receiver_thread
            if stale and stale.is_alive():
                stale.join(timeout=2.0)
            if stale and stale.is_alive():
                logger.warning("Olympus: previous liveview receiver still holds the UDP port; abandoning it")
            self._receiver_thread = None
            self._receiver = None
            self._receiver_orphaned = False

        if self._receiver is None:
            self._receiver = LiveViewReceiver(self._frame_queue)
        if self._receiver_thread is None or not self._receiver_thread.is_alive():
            self._receiver_thread = threading.Thread(
                target=self._receiver.receive_packets,
                args=(self._config.liveview_port,),
                name="OlympusLiveViewUDP",
                daemon=True,
            )
            self._receiver_thread.start()

    def _start_liveview(self) -> None:
        if self._liveview_active:
            return

        # while a capture is downloading, or during the post-capture display
        # freeze, the livestream stays suppressed (the loop serves a placeholder
        # instead), so the frontend shows only the photo.
        if self._is_frozen():
            logger.debug("Olympus: liveview suppressed during capture/display freeze")
            return

        if self._camera is None and not self._connect():
            return

        assert self._camera is not None

        try:
            # The UDP receiver must bind the local port before the camera is
            # told to broadcast, so start it first.
            self._ensure_receiver()

            run_bounded(
                self._camera.start_liveview, self._config.liveview_port, self._lvqty or OlympusCamera.DEFAULT_RES, timeout=3.0, desc="start_liveview"
            )
            self._liveview_active = True
            self._last_frame_time = time.monotonic()
            logger.info("Olympus: liveview started.")
        except Exception as exc:
            logger.warning(f"Olympus: could not start liveview: {exc}")
            self._liveview_active = False
            invalidate_camera_calls()
            self._camera = None  # force a fresh connect on the next attempt

    def _stop_liveview(self) -> None:
        if self._camera:
            try:
                run_bounded(self._camera.stop_liveview, timeout=2.0, desc="stop_liveview")
            except Exception as exc:
                logger.debug(f"Olympus: error stopping liveview: {exc}")
        self._liveview_active = False
        # The UDP receiver thread stays alive and keeps the port bound; it is
        # only torn down in teardown_resource().

    # ------------------------------------------------------------------
    # Resource lifecycle (managed by ResilientService)
    # ------------------------------------------------------------------
    def setup_resource(self):
        self._frame_queue = queue.SimpleQueue()
        self._receiver = LiveViewReceiver(self._frame_queue)

        if not self._connect():
            # Raising lets ResilientService retry periodically in the
            # background, so the app keeps loading while the camera is off.
            ip = self._config.device_ip or DEFAULT_CAMERA_WIFI_IP
            raise ConnectionError(f"Olympus camera not reachable on {ip}. Is the camera in wifi mode?")

    def teardown_resource(self):
        # Stop the broadcast FIRST. ``LiveViewReceiver.receive_packets`` re-reads
        # its ``running`` flag only after a recv timeout (1s); while the camera
        # keeps streaming, recv never times out, so ``shut_down()`` alone never
        # unblocks the thread and its UDP socket stays bound. Stopping the camera
        # broadcast makes recv time out, the loop then breaks and the socket
        # closes (bounded, so an unreachable camera cannot hang shutdown).
        self._stop_liveview()
        if self._receiver:
            self._receiver.shut_down()
        receiver_thread = self._receiver_thread
        if receiver_thread and receiver_thread.is_alive():
            receiver_thread.join(timeout=3.0)
        # Only release the references once the socket-owning thread has actually
        # ended; if it somehow survived (stop failed while the camera kept
        # streaming), retain it rather than leaking the bound port to a
        # double-bind - a replacement receiver must not bind while this port is
        # still occupied.
        if receiver_thread is None or not receiver_thread.is_alive():
            self._receiver_thread = None
            self._receiver = None
            self._receiver_orphaned = False
        else:
            # retained: the old thread still owns the bound port; the next
            # session must reap it before creating a replacement receiver.
            self._receiver_orphaned = True

        # drop any queued camera call of this session before it acts on a newer one
        invalidate_camera_calls()
        self._camera = None
        self._lvqty = None
        self._liveview_active = False
        self._liveview_start_failures = 0
        # Invalidate and stop any in-flight capture worker. It runs on its own
        # daemon thread and never checks stop, so on shutdown it must be told
        # its session is over (bump the generation) and joined (bounded) before
        # we reset the shared state it would otherwise clobber.
        self._capture_generation += 1
        if self._capture_thread and self._capture_thread.is_alive():
            self._capture_thread.join(timeout=10)
        self._capture_thread = None
        self._freeze_until = 0.0
        self._capture_in_progress = False
        self._placeholder = None

        # Invalidate the mode machine so it re-initializes on the next start
        # (needed for liveview to be restarted after a reconnect).
        self._mode_machine.active_mode = None

        # drop stale frames from a previous session
        try:
            while True:
                self._frame_queue.get_nowait()
        except queue.Empty:
            pass

    # ------------------------------------------------------------------
    # Main worker loop
    # ------------------------------------------------------------------
    def run_service(self):
        # apply the initial (standby) mode so the mode machine is in a defined state
        self._mode_machine.process_switchmode()

        while not self._stop_event.is_set():
            # ------------------------------------------------------------------
            # 1) a still capture is downloading in its own background thread:
            #    freeze the livestream and serve a placeholder so the frontend
            #    never times out or sees a live feed during the download.
            # ------------------------------------------------------------------
            if self._capture_in_progress:
                self._publish_placeholder()
                time.sleep(0.05)
                continue

            # 2) pending hires capture request (from wait_for_still_file)
            with self._hires_lock:
                req = self._hires_queue.popleft() if self._hires_queue else None

            if req:
                if isinstance(req, StillRequest):
                    self._begin_capture(req)
                else:
                    logger.warning(f"Olympus backend does not support {type(req)} requests")
                continue

            # 3) apply any requested mode change
            self._mode_machine.process_switchmode()

            # 4) during the post-capture display freeze, keep serving the
            #    placeholder instead of live frames.
            if self._is_frozen():
                self._publish_placeholder()
                time.sleep(0.05)
                continue

            # 5) serve liveview frames only while in video mode.
            if self._mode_machine.active_mode != "video":
                time.sleep(0.2)
                continue

            # make sure the liveview is actually streaming (it started on the
            # transition to video mode, but ensure it here too in case a drop)
            self._start_liveview()
            if not self._liveview_active:
                # While we wait to (re)start the stream (a camera busy after a
                # capture can take a while to answer start_liveview), keep
                # serving the placeholder so the websocket never times out and
                # closes the stream — otherwise the frontend falls into the
                # stuck "no stream" state during the second collage shot.
                self._publish_placeholder()
                # back off with bounds instead of hammering a tight reconnect
                # loop.
                self._liveview_start_failures += 1
                delay = self._liveview_retry_delay()
                logger.debug(f"Olympus: liveview not active (failure #{self._liveview_start_failures}), retrying in {delay:.1f}s")
                if self._stop_event.wait(timeout=delay):
                    return  # shutdown requested while waiting
                continue
            self._liveview_start_failures = 0

            # self-heal: restart the UDP thread if it died while in video mode
            self._ensure_receiver()

            try:
                frame = self._frame_queue.get(timeout=0.2)
            except queue.Empty:
                # No new frame this read. A healthy stream delivers ~15fps, so a
                # sustained gap while liveview is active means the camera
                # stopped sending RTP (power cycle / lost liveview subscription):
                # the receiver keeps living across socket timeouts and
                # _start_liveview would early-return on the stale flag, so we'd
                # never reconnect. Detect the stall, drop _liveview_active so the
                # next iteration resubscribes (serving the placeholder + backoff
                # meanwhile).
                if self._liveview_active and self._last_frame_time and (time.monotonic() - self._last_frame_time > self.LIVEVIEW_STALL_TIMEOUT):
                    logger.warning(f"Olympus: liveview stalled ({time.monotonic() - self._last_frame_time:.0f}s without a frame); resubscribing")
                    self._liveview_active = False
                    self._liveview_start_failures = 0
                    # drop stale frames from the dead stream
                    try:
                        while True:
                            self._frame_queue.get_nowait()
                    except queue.Empty:
                        pass
                continue
            while True:
                try:
                    frame = self._frame_queue.get_nowait()
                except queue.Empty:
                    break

            with self._lores_data[0].condition:
                self._lores_data[0].data = frame.jpeg
                self._lores_data[0].condition.notify_all()
            self._last_frame_time = time.monotonic()
            self._frame_tick()

            # the UDP receiver can deliver faster than needed; cap the publish rate
            self._framerate.wait_until_fps(15)

    # ------------------------------------------------------------------
    # Liveview freeze helpers
    # ------------------------------------------------------------------
    def _is_frozen(self) -> bool:
        """True while a still is downloading or during the post-capture freeze."""
        return self._capture_in_progress or time.monotonic() < self._freeze_until

    def _liveview_retry_delay(self) -> float:
        """Exponential backoff (bounded) before retrying a failed liveview start."""
        return min(0.2 * (2 ** min(self._liveview_start_failures, 4)), 5.0)

    def _publish_placeholder(self) -> None:
        """Broadcast a static \"busy\" frame to the lores stream.

        Keeps the frontend websocket fed (so it never runs into its retry
        timeouts) while the camera feed is intentionally suppressed during a
        capture and its display. Does nothing if building the frame failed.
        """
        if self._placeholder is None:
            self._placeholder = make_placeholder_jpeg()
        if not self._placeholder:
            return
        with self._lores_data[0].condition:
            self._lores_data[0].data = self._placeholder
            self._lores_data[0].condition.notify_all()

    # ------------------------------------------------------------------
    # Still capture
    # ------------------------------------------------------------------
    def _begin_capture(self, req: StillRequest) -> None:
        """Start a still capture in a background thread and freeze the liveview.

        The shutter + poll + wifi download run in a dedicated thread so the
        worker loop can keep serving the placeholder to the lores stream; the
        frontend is never left timing out during the (multi-second) download.

        A generation token is bumped and passed to the worker: if a newer
        capture starts or teardown runs, the old worker detects it is superseded
        and stops before delivering or touching shared state.
        """
        self._capture_generation += 1
        gen = self._capture_generation
        self._capture_in_progress = True
        self._capture_thread = threading.Thread(
            target=self._capture_worker,
            name="OlympusStillCapture",
            args=(req, gen),
            daemon=True,
        )
        self._capture_thread.start()

    def _capture_stale(self, gen: int) -> bool:
        """True when this capture session was superseded (a newer capture or a
        teardown/shutdown). The worker must then stop performing camera calls
        and stop updating shared state: teardown or the newer session own it.
        """
        return self._stop_event.is_set() or gen != self._capture_generation

    def _capture_worker(self, req: StillRequest, gen: int) -> None:
        """Shutter, download and deliver a still, off the worker thread.

        Runs in a background thread (see ``_begin_capture``). The result is
        delivered via the request; a timeout (camera alive but no image) or a
        connection error leaves the request unsatisfied so ``wait_for_still_file``
        raises its own ``TimeoutError``.
        """
        if self._capture_stale(gen):
            return

        poll_timeout = self._config.capture_timeout

        try:
            if self._camera is None and not self._connect():
                raise ConnectionError("Olympus camera is not reachable (off or wifi disconnected).")
            if self._capture_stale(gen):
                return

            assert self._camera is not None

            with self._mode_machine.ext_mode_switch_lock:
                self._mode_machine.process_switchmode("still")

            # remember which files already exist on the card before shooting
            before_files = run_bounded(self._camera.list_images, timeout=3.0, desc="list_images(initial)") or []
            before = {img.file_name: img.date_time for img in before_files}
            if self._capture_stale(gen):
                return

            logger.info("Olympus: triggering shutter...")
            run_bounded(self._camera.take_picture, timeout=12.0, desc="take_picture")

            # freeze the live stream now that the shutter fired: the frontend is
            # served the placeholder for the rest of the capture + display.
            self._stop_liveview()

            poll_deadline = time.time() + poll_timeout

            new_image = None
            busy_streak = 0
            while time.time() < poll_deadline:
                time.sleep(0.8)
                if self._capture_stale(gen):
                    return
                if self._camera is None:
                    if not self._connect():
                        logger.warning("Olympus: camera not reachable during capture poll")
                        continue
                    if self._camera is None:
                        continue
                try:
                    images = (
                        run_bounded(
                            self._camera.list_images,
                            timeout=4.0,
                            desc="list_images(poll)",
                        )
                        or []
                    )
                except Exception as exc:
                    busy_streak += 1
                    logger.debug(f"Olympus: list_images during capture failed ({busy_streak}): {exc}")
                    # Repeated errors (esp. OSC errorcode=1001 = camera busy)
                    # mean the camera is still finishing the capture or stuck in
                    # a record/shutter mode where get_imglist is refused. Reset
                    # the connection instead of hammering the same wedged
                    # session - a fresh object re-reads the camera state and
                    # mode, so the next list_images has a clean shot.
                    if busy_streak >= 5:
                        busy_streak = 0
                        logger.warning("Olympus: persistent busy during capture poll, resetting connection")
                        invalidate_camera_calls()
                        self._camera = None
                        self._liveview_active = False
                    continue
                busy_streak = 0
                added = [img for img in images if img.file_name not in before and Path(img.file_name).suffix.lower() in (".jpg", ".jpeg")]
                if added:
                    # pick the most recent new JPEG: robust to JPG+RAW and to
                    # the camera reporting files out of order.
                    new_image = max(added, key=lambda img: (img.date_time, img.file_name))
                    break

            if self._capture_stale(gen):
                return

            if new_image is None:
                # leave the request unsatisfied; wait_for_still_file raises its
                # own TimeoutError. The camera is fine, so don't reset it.
                raise TimeoutError(f"Olympus: no new image appeared within {poll_timeout:.1f}s.")

            if self._capture_stale(gen):
                return

            logger.info(f"Olympus: downloading {new_image.file_name}...")
            # download_image(path) returns the full-size JPEG as bytes. The
            # transfer limit comes from config (capture_timeout only bounds the
            # polling above), so a slow wifi AP can be given more headroom.
            assert self._camera is not None
            jpeg_bytes = run_bounded(
                self._camera.download_image,
                new_image.file_name,
                timeout=self._config.download_timeout,
                desc=f"download_image({new_image.file_name})",
            )
            if jpeg_bytes is None:
                raise RuntimeError("Olympus: download_image returned no data.")

            with NamedTemporaryFile(
                mode="wb",
                delete=False,
                # write on the media filesystem ("tmp") so renaming the delivered
                # capture into ./media works; gettempdir() (/tmp tmpfs) would
                # raise EXDEV when renamed across filesystems.
                dir="tmp",
                prefix=f"{filename_str_time()}_olympus_",
                suffix=".jpg",
            ) as jpeg_file:
                jpeg_file.write(jpeg_bytes)
                filepath = Path(jpeg_file.name)

            # only deliver if this is still the live session
            if self._capture_stale(gen):
                return

            with req.condition:
                req.result_file = filepath
                req.condition.notify_all()

            logger.info("Olympus: still delivered.")
        except TimeoutError:
            logger.warning(f"Olympus: capture timed out after {poll_timeout:.1f}s without a new image.")
        except Exception as exc:
            logger.error(f"Olympus: capture failed: {exc}")
            if not self._capture_stale(gen):
                invalidate_camera_calls()
                self._camera = None
                self._liveview_active = False
        finally:
            # Only the still-live session may perform cleanup and the display
            # freeze; a superseded worker must not touch shared state owned by
            # teardown or a newer capture.
            if not self._capture_stale(gen):
                # ensure the liveview stays off and the display freeze starts,
                # so the livestream does not jump back in before the photo is
                # shown.
                try:
                    self._stop_liveview()
                except Exception as exc:
                    logger.debug(f"Olympus: error stopping liveview after capture: {exc}")

                self._freeze_until = time.monotonic() + self._settle_after_capture
                self._capture_in_progress = False
                logger.debug(f"Olympus: capture done, live frozen {self._settle_after_capture:.1f}s for display")
