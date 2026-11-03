"""Olympus wifi backend for photobooth.

Drives a wifi-enabled Olympus camera through the ``olympuswifi`` library
(https://olympus-wifi.readthedocs.io). The camera acts as its own wifi access
point and always exposes its control interface at 192.168.0.10, so the backend
connects directly to that address (the ``device_ip`` config value is only
informational for this backend).

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
from tempfile import NamedTemporaryFile, gettempdir

from olympuswifi.camera import OlympusCamera
from olympuswifi.liveview import LiveViewReceiver

from ...utils.helper import filename_str_time
from ..config.groups.cameras import GroupCameraOlympus
from .abstractbackend import AbstractBackend, StillRequest

logger = logging.getLogger(__name__)

# Fixed well-known address of an Olympus wifi camera.
CAMERA_WIFI_IP = "192.168.0.10"


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
        resolutions = [
            str(option)
            for option in (lvqty or {})
            if isinstance(option, str) and re.fullmatch(r"\d+x\d+", option)
        ]
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


class OlympusBackend(AbstractBackend):
    """Backend for wifi-enabled Olympus cameras via the ``olympuswifi`` library."""

    def __init__(self, config: GroupCameraOlympus):
        super().__init__(
            # GroupCameraOlympus has no orientation field yet; keep a sane default.
            orientation=getattr(config, "orientation", "1: 0°"),
            num_subdevices=1,
            idle_timeout=(
                config.camera_standby_when_inactive_time
                if config.camera_standby_when_inactive
                else None
            ),
        )
        self._config = config

        self._camera: OlympusCamera | None = None
        self._receiver: LiveViewReceiver | None = None
        self._receiver_thread: threading.Thread | None = None
        self._frame_queue: queue.SimpleQueue = queue.SimpleQueue()
        # liveview resolution, read lazily from the camera on first connect
        self._lvqty: str | None = None
        # whether a liveview is currently streaming from the camera
        self._liveview_active: bool = False
        # post-capture settle: the backend stays out of liveview for a short
        # beat after a still, so the after-screen is not flooded with frames.
        self._settle_after_capture: float = config.camera_settle_after_capture
        self._still_until: float = 0.0

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

        try:
            camera = OlympusCamera()  # contacts http://192.168.0.10/
            info = camera.get_camera_info()
            if not info or "model" not in info:
                logger.warning(f"Olympus camera did not answer on {CAMERA_WIFI_IP}.")
                return False

            self._camera = camera
            self._lvqty = select_liveview_quality(camera)
            self._liveview_active = False  # fresh camera object -> fresh state
            logger.info(f"Connected to Olympus {info.get('model')}.")
            return True
        except Exception as exc:
            logger.warning(f"Olympus camera not reachable ({CAMERA_WIFI_IP}): {exc}")
            self._camera = None
            return False

    # ------------------------------------------------------------------
    # Liveview
    # ------------------------------------------------------------------
    def _start_liveview(self) -> None:
        if self._liveview_active:
            return

        # enforce a short post-capture hold before the livestream resumes, so
        # the captured photo stays on the after-screen a moment longer.
        remaining = self._still_until - time.monotonic()
        if remaining > 0:
            logger.debug(f"Olympus: holding {remaining:.2f}s before resuming liveview")
            if self._stop_event.wait(timeout=remaining):
                return  # shutdown requested while waiting

        if self._camera is None and not self._connect():
            return

        assert self._camera is not None

        try:
            # The UDP receiver must bind the local port before the camera is
            # told to broadcast, so start it first. receive_packets(port) binds
            # the socket, hence the explicit port argument.
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

            self._camera.start_liveview(
                port=self._config.liveview_port,
                lvqty=self._lvqty or OlympusCamera.DEFAULT_RES,
            )
            self._liveview_active = True
            logger.info("Olympus: liveview started.")
        except Exception as exc:
            logger.warning(f"Olympus: could not start liveview: {exc}")
            self._liveview_active = False
            self._camera = None  # force a fresh connect on the next attempt

    def _stop_liveview(self) -> None:
        if self._camera:
            try:
                self._camera.stop_liveview()
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
            raise ConnectionError(
                f"Olympus camera not reachable on {CAMERA_WIFI_IP}. "
                "Is the camera in wifi mode?"
            )

    def teardown_resource(self):
        if self._receiver_thread and self._receiver_thread.is_alive():
            if self._receiver:
                self._receiver.shut_down()
            self._receiver_thread.join(timeout=3.0)
        self._receiver_thread = None
        self._receiver = None

        if self._camera:
            try:
                self._camera.stop_liveview()
            except Exception as exc:
                logger.debug(f"Olympus: error stopping liveview: {exc}")
        self._camera = None
        self._lvqty = None
        self._liveview_active = False
        self._still_until = 0.0

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
            # 1) pending hires capture request (from wait_for_still_file)
            with self._hires_lock:
                req = self._hires_queue.popleft() if self._hires_queue else None

            if req:
                if isinstance(req, StillRequest):
                    self._capture_still(req)
                else:
                    logger.warning(f"Olympus backend does not support {type(req)} requests")
                continue

            # 2) apply any requested mode change
            self._mode_machine.process_switchmode()

            # 3) serve liveview frames only while in video mode. In still mode
            #    the frontend shows the captured photo, so no frames flow and
            #    the livestream does not jump back in immediately after a shot.
            if self._mode_machine.active_mode != "video":
                time.sleep(0.2)
                continue

            try:
                frame = self._frame_queue.get(timeout=0.2)
            except queue.Empty:
                # no new frame yet; do not busy-loop
                continue

            with self._lores_data[0].condition:
                self._lores_data[0].data = frame.jpeg
                self._lores_data[0].condition.notify_all()
            self._frame_tick()

            # the UDP receiver can deliver faster than needed; cap the publish rate
            self._framerate.wait_until_fps(15)

    # ------------------------------------------------------------------
    # Still capture
    # ------------------------------------------------------------------
    def _capture_still(self, req: StillRequest) -> None:
        """Fire the shutter, download the newest image and deliver it to ``req``.

        Any error propagates out of ``run_service`` so that ResilientService
        tears down (closing a possibly stale connection) and reconnects.
        """
        if self._camera is None and not self._connect():
            raise ConnectionError("Olympus camera is not reachable (off or wifi disconnected).")

        assert self._camera is not None

        try:
            with self._mode_machine.ext_mode_switch_lock:
                self._mode_machine.process_switchmode("still")

            # remember which files already exist on the card before shooting
            before = {image.file_name for image in self._camera.list_images()}

            logger.info("Olympus: triggering shutter...")
            self._camera.take_picture()

            new_file = None
            deadline = time.time() + self._config.capture_timeout
            while time.time() < deadline:
                time.sleep(0.5)
                try:
                    images = self._camera.list_images()
                except Exception as exc:
                    logger.debug(f"Olympus: list_images during capture failed: {exc}")
                    continue
                added = [image.file_name for image in images if image.file_name not in before]
                if added:
                    # camera filenames are sequential -> first new one is the shot
                    new_file = added[0]
                    break

            if new_file is None:
                raise TimeoutError(
                    f"Olympus: no new image appeared within {self._config.capture_timeout}s."
                )

            logger.info(f"Olympus: downloading {new_file}...")
            # download_image(path) returns the full-size JPEG as bytes
            jpeg_bytes = self._camera.download_image(new_file)

            with NamedTemporaryFile(
                mode="wb",
                delete=False,
                dir=gettempdir(),
                prefix=f"{filename_str_time()}_olympus_",
                suffix=".jpg",
            ) as jpeg_file:
                jpeg_file.write(jpeg_bytes)
                filepath = Path(jpeg_file.name)

            with req.condition:
                req.result_file = filepath
                req.condition.notify_all()

            # post-capture settling: stop the liveview and stay out of it for a
            # short beat so the captured photo is shown before liveview resumes.
            # Stopping after delivery ensures the shutter had the liveview it
            # may need, and keeps the camera out of record mode between shots.
            try:
                self._stop_liveview()
            except Exception as exc:
                logger.debug(f"Olympus: error stopping liveview after capture: {exc}")
            self._still_until = time.monotonic() + self._settle_after_capture
        except Exception as exc:
            # mark the camera as disconnected so a fresh connection is created
            # on the next attempt (e.g. battery died mid-capture)
            self._camera = None
            self._liveview_active = False
            raise RuntimeError(f"Olympus capture failed: {exc}") from exc
