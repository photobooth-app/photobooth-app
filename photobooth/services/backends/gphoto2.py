"""
Gphoto2 backend implementation

"""
import dataclasses
import logging
import time
from threading import Condition, Event

import gphoto2 as gp

from ...utils.stoppablethread import StoppableThread
from ..config import appconfig
from .abstractbackend import AbstractBackend

logger = logging.getLogger(__name__)


class Gphoto2Backend(AbstractBackend):
    """
    The backend implementation using gphoto2
    """

    @dataclasses.dataclass
    class Gphoto2DataBytes:
        """
        bundle data bytes and it's condition.
        1) save some instance attributes and
        2) bundle as it makes sense
        """

        # jpeg data as bytes
        data: bytes = None
        # signal to producer that requesting thread is ready to be notified
        request_ready: Event = None
        # condition when frame is avail
        condition: Condition = None

    def __init__(self):
        super().__init__()

        self._camera = gp.Camera()
        self._camera_context = gp.Context()

        self._hires_data: __class__.Gphoto2DataBytes = __class__.Gphoto2DataBytes(
            data=None,
            request_ready=Event(),
            condition=Condition(),
        )
        self._lores_data: __class__.Gphoto2DataBytes = __class__.Gphoto2DataBytes(
            data=None,
            condition=Condition(),
        )

        # worker threads
        self._worker_thread: StoppableThread = None

        logger.info(f"python-gphoto2: {gp.__version__}")
        logger.info(f"libgphoto2: {gp.gp_library_version(gp.GP_VERSION_VERBOSE)}")
        logger.info(f"libgphoto2_port: {gp.gp_port_library_version(gp.GP_VERSION_VERBOSE)}")

        # enable logging to python. need to store callback, otherwise logging does not work.
        # gphoto2 logging is too verbose, reduce mapping
        self._logger_callback = gp.check_result(
            gp.use_python_logging(
                mapping={
                    gp.GP_LOG_ERROR: logging.INFO,
                    gp.GP_LOG_DEBUG: logging.DEBUG - 1,
                    gp.GP_LOG_VERBOSE: logging.DEBUG - 3,
                    gp.GP_LOG_DATA: logging.DEBUG - 6,
                }
            )
        )

    def _device_start(self):
        # start camera
        try:
            self._camera = gp.Camera()  # better use fresh object.
            self._camera.init()  # if init was success, the backend is ready to deliver, no additional later checks needed.
        except gp.GPhoto2Error as exc:
            logger.exception(exc)
            logger.critical("camera failed to initialize. no power? no connection? cam on standby?")
            raise RuntimeError("failed to start up backend") from exc

        if appconfig.backends.LIVEPREVIEW_ENABLED:
            self._check_camera_preview_available()

        self._worker_thread = StoppableThread(name="gphoto2_worker_thread", target=self._worker_fun, daemon=True)
        self._worker_thread.start()

        # short sleep until backend started.
        time.sleep(0.5)

        logger.debug(f"{self.__module__} started")

    def _device_stop(self):
        # supervising connection thread was asked to stop - so we ask to stop worker fun also
        if self._worker_thread:
            self._worker_thread.stop()
            self._worker_thread.join()

        if self._camera:
            self._camera.exit()

        logger.debug(f"{self.__module__} stopped")

    def _device_available(self):
        """
        For gphoto2 right now we just check if anything is there; if so we use that.
        Could add connect to specific device in future.
        """
        return len(available_camera_indexes()) > 0

    def _wait_for_hq_image(self):
        """
        for other threads to receive a hq JPEG image
        mode switches are handled internally automatically, no separate trigger necessary
        this function blocks until frame is received
        raise TimeoutError if no frame was received
        """
        with self._hires_data.condition:
            self._hires_data.request_ready.set()

            if not self._hires_data.condition.wait(timeout=4):
                raise TimeoutError("timeout receiving frames")

        self._hires_data.request_ready.clear()
        return self._hires_data.data

    #
    # INTERNAL FUNCTIONS
    #

    def _check_camera_preview_available(self):
        """Test on init whether preview is available for this camera."""
        try:
            self._camera.capture_preview()
        except Exception as exc:
            logger.info(f"gather preview failed; disabling preview in this session. consider to disable permanently! {exc}")
        else:
            logger.info("preview is available")

    def _wait_for_lores_image(self):
        """for other threads to receive a lores JPEG image"""
        with self._lores_data.condition:
            if not self._lores_data.condition.wait(timeout=0.2):
                raise TimeoutError("timeout receiving frames")

            return self._lores_data.data

    def _on_configure_optimized_for_hq_capture(self):
        self._iso(appconfig.backends.gphoto2_iso_capture)
        self._shutter_speed(appconfig.backends.gphoto2_shutter_speed_capture)

    def _on_configure_optimized_for_idle(self):
        self._iso(appconfig.backends.gphoto2_iso_liveview)
        self._shutter_speed(appconfig.backends.gphoto2_shutter_speed_liveview)

    def _iso(self, val: str = ""):
        if not val:
            logger.debug("iso empty, ignore")
            return
        try:
            logger.info(f"setting custom iso value: {val}")
            self._gp_set_config("iso", val)
        except gp.GPhoto2Error as exc:
            logger.warning(f"cannot set iso, command ignored {exc}")

    def _shutter_speed(self, val: str = ""):
        if not val:
            logger.debug("shutter speed empty, ignore")
            return
        try:
            logger.info(f"setting custom shutter speed: {val}")
            self._gp_set_config("shutterspeed", val)
        except gp.GPhoto2Error as exc:
            logger.warning(f"cannot set shutter speed, command ignored {exc}")

    def _viewfinder(self, val=0):
        try:
            self._gp_set_config("viewfinder", val)
        except gp.GPhoto2Error as exc:
            logger.warning(f"cannot set viewfinder, command ignored {exc}")

    def _gp_set_config(self, name, val):
        config = self._camera.get_config(self._camera_context)
        node = config.get_child_by_name(name)
        node.set_value(val)
        self._camera.set_config(config, self._camera_context)

    #
    # INTERNAL IMAGE GENERATOR
    #

    def _worker_fun(self):
        preview_failcounter = 0

        while not self._worker_thread.stopped():  # repeat until stopped
            if not self._hires_data.request_ready.is_set():
                if appconfig.backends.LIVEPREVIEW_ENABLED:
                    try:
                        capture = self._camera.capture_preview()

                    except Exception as exc:
                        preview_failcounter += 1

                        if preview_failcounter <= 10:
                            logger.warning(f"error capturing frame from DSLR: {exc}")
                            # abort this loop iteration and continue sleeping...
                            time.sleep(0.5)  # add another delay to avoid flooding logs

                            continue
                        else:
                            logger.critical(f"aborting capturing frame, camera disconnected? retry to connect {exc}")
                            self._camera.exit()
                            self.device_set_status_fault_flag()
                            break
                    else:
                        preview_failcounter = 0

                    img_bytes = memoryview(capture.get_data_and_size()).tobytes()

                    with self._lores_data.condition:
                        self._lores_data.data = img_bytes
                        self._lores_data.condition.notify_all()
                else:
                    time.sleep(0.05)
            else:
                # only capture one pic and return to lores streaming afterwards
                self._hires_data.request_ready.clear()

                # disable viewfinder;
                # allows camera to autofocus fast in native mode not contrast mode
                if appconfig.backends.gphoto2_disable_viewfinder_before_capture:
                    logger.info("disable viewfinder before capture")
                    self._viewfinder(0)

                # capture hq picture
                logger.info("taking hq picture")
                try:
                    file_path = self._camera.capture(gp.GP_CAPTURE_IMAGE)

                    logger.info(f"Camera file path: {file_path.folder}/{file_path.name}")

                except gp.GPhoto2Error as exc:
                    logger.critical(f"error capture! check logs for errors. {exc}")

                    # try again in next loop
                    continue

                self._iso(appconfig.backends.gphoto2_iso_liveview)
                self._shutter_speed(appconfig.backends.gphoto2_shutter_speed_liveview)

                # read from camera
                try:
                    if appconfig.backends.gphoto2_wait_event_after_capture_trigger:
                        self._camera.wait_for_event(1000)

                    camera_file = self._camera.file_get(
                        file_path.folder,
                        file_path.name,
                        gp.GP_FILE_TYPE_NORMAL,
                    )

                    file_data = camera_file.get_data_and_size()
                    img_bytes = memoryview(file_data).tobytes()
                except gp.GPhoto2Error as exc:
                    logger.critical(f"error reading camera file! check logs for errors. {exc}")

                    # try again in next loop
                    continue

                with self._hires_data.condition:
                    self._hires_data.data = img_bytes

                    self._hires_data.condition.notify_all()

        logger.warning("_worker_fun exits")


def available_camera_indexes():
    """
    find available cameras, return valid indexes.
    """

    camera_list = gp.Camera.autodetect()
    if len(camera_list) == 0:
        logger.info("no camera detected")
        return []

    available_indexes = []
    for index, (name, addr) in enumerate(camera_list):
        available_indexes.append(index)
        logger.info(f"found camera - {index}:  {addr}  {name}")

    return available_indexes
