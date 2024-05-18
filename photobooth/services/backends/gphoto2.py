"""
Gphoto2 backend implementation

"""

import dataclasses
import logging
import os
import time
from threading import Condition, Event

import gphoto2 as gp

from ...utils.stoppablethread import StoppableThread
from ..config.groups.backends import GroupBackendGphoto2
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
        request_hires_still: Event = None
        # condition when frame is avail
        condition: Condition = None

    def __init__(self, config: GroupBackendGphoto2):
        self._config: GroupBackendGphoto2 = config
        super().__init__()

        self._camera = gp.Camera()
        self._camera_context = gp.Context()

        # if True signal to switch optimized, set none after switch again.
        self._configure_optimized_for_hq_capture_flag = None
        self._configure_optimized_for_idle_flag = None

        # generate dict for clear events clear text names
        # defined events http://www.gphoto.org/doc/api/gphoto2-camera_8h.html#a438ab2ac60ad5d5ced30e4201476800b
        self.event_texts = {}
        for name in (
            "GP_EVENT_UNKNOWN",
            "GP_EVENT_TIMEOUT",
            "GP_EVENT_FILE_ADDED",
            "GP_EVENT_FOLDER_ADDED",
            "GP_EVENT_CAPTURE_COMPLETE",
            "GP_EVENT_FILE_CHANGED",
        ):
            self.event_texts[getattr(gp, name)] = name

        self._hires_data: __class__.Gphoto2DataBytes = __class__.Gphoto2DataBytes(
            data=None,
            request_hires_still=Event(),
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

    def _block_until_delivers_lores_images(self):
        # backend doesn't support reliable preview delivery (depends on dslr), so this check is removed by overriding the parent class function
        pass

    def _device_start(self):
        # start camera
        try:
            self._camera = gp.Camera()  # better use fresh object.
            self._camera.init()  # if init was success, the backend is ready to deliver, no additional later checks needed.
        except gp.GPhoto2Error as exc:
            logger.exception(exc)
            logger.critical("camera failed to initialize. no power? no connection? cam on standby?")
            raise RuntimeError("failed to start up backend") from exc

        try:
            logger.info(str(self._camera.get_summary()))
            config = self._camera.list_config()
            for n in range(len(config)):
                logger.debug(f"{config.get_name(n)}={config.get_value(n)}")
        except gp.GPhoto2Error as exc:
            logger.error(f"could not get camera information, error {exc}")

        self._capturetarget(self._config.gcapture_target)

        self._worker_thread = StoppableThread(name="gphoto2_worker_thread", target=self._worker_fun, daemon=True)
        self._worker_thread.start()

        # short sleep until backend started.
        time.sleep(0.5)

        # wait until threads are up and deliver images actually. raises exceptions if fails after several retries
        # this backend doesn't support this, the function is overridden in this class and does just nothing
        self._block_until_delivers_lores_images()

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
            self._hires_data.request_hires_still.set()

            if not self._hires_data.condition.wait(timeout=8):
                self._hires_data.request_hires_still.clear()  # clear hq request even if failed, parent class might retry again
                raise TimeoutError("timeout receiving frames")

        return self._hires_data.data

    #
    # INTERNAL FUNCTIONS
    #

    def _wait_for_lores_image(self):
        """for other threads to receive a lores JPEG image"""
        flag_logmsg_emitted_once = False
        while self._hires_data.request_hires_still.is_set():
            if not flag_logmsg_emitted_once:
                logger.debug("request to _wait_for_lores_image waiting until ongoing request_hires_still is finished")
                flag_logmsg_emitted_once = True  # avoid flooding logs

            time.sleep(0.2)

        with self._lores_data.condition:
            if not self._lores_data.condition.wait(timeout=0.5):
                raise TimeoutError("timeout receiving frames")

            return self._lores_data.data

    def _on_configure_optimized_for_hq_capture(self):
        self._configure_optimized_for_hq_capture_flag = True

    def _on_configure_optimized_for_idle(self):
        self._configure_optimized_for_idle_flag = True

    def _configure_optimized_for_hq_capture(self):
        if self._configure_optimized_for_hq_capture_flag:
            logger.debug("configure camera optimized for still capture")
            self._configure_optimized_for_hq_capture_flag = None
            self._iso(self._config.iso_capture)
            self._shutter_speed(self._config.shutter_speed_capture)

    def _configure_optimized_for_idle(self):
        if self._configure_optimized_for_idle_flag:
            logger.debug("configure camera optimized for idle/video")
            self._configure_optimized_for_idle_flag = None
            self._iso(self._config.iso_liveview)
            self._shutter_speed(self._config.shutter_speed_liveview)

    def _capturetarget(self, val: str = ""):
        if not val:
            logger.debug("capturetarget empty, ignore")
            return
        try:
            logger.info(f"setting capturetarget value: {val}")
            self._gp_set_config("capturetarget", val)
        except gp.GPhoto2Error as exc:
            logger.warning(f"cannot set capturetarget, command ignored {exc}")

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
            if not self._hires_data.request_hires_still.is_set():
                if self.device_enable_lores_stream:
                    # check if flag is true and configure if so once.
                    self._configure_optimized_for_idle()

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
                # hold a list of captured files during capture. this is needed if JPG+RAW is shot.
                # there is no guarantee that the first is the JPG and second the RAW image. Also depending on the capturetarget
                # the sequence the images appear can be different. gp.GP_CAPTURE_IMAGE vs gp.GP_CAPTURE_RAW seems not reliable to rely on
                captured_files: list[tuple[str:str]] = []

                # disable viewfinder;
                # allows camera to autofocus fast in native mode not contrast mode
                if self._config.disable_viewfinder_before_capture:
                    logger.info("disable viewfinder before capture")
                    self._viewfinder(0)

                # check if flag is true and configure if so once.
                self._configure_optimized_for_hq_capture()

                # capture hq picture
                logger.info("taking hq picture")
                try:
                    file_path = self._camera.capture(gp.GP_CAPTURE_IMAGE)
                    captured_files.append((file_path.folder, file_path.name))
                except gp.GPhoto2Error as exc:
                    logger.critical(f"error capture! check logs for errors. {exc}")

                    # try again in next loop
                    continue

                # empty the event queue, needed in case of RAW+JPG shooting usually.
                # used usually only if capture JPG+RAW enabled (2 files added in one capture)
                # if not cleared, the second capture might fail due to pending events in libgphoto2
                # also if raw, we might have the JPG added later in these events, not received from .capture above
                # https://github.com/jim-easterbrook/python-gphoto2/issues/65#issuecomment-433615025
                evt_typ, evt_data = self._camera.wait_for_event(200)
                while evt_typ != gp.GP_EVENT_TIMEOUT:
                    logger.debug(f"Event: {self.event_texts.get(evt_typ,f'unknown event index: {evt_typ}')}, data: {evt_data}")

                    if evt_typ == gp.GP_EVENT_FILE_ADDED:
                        captured_files.append((evt_data.folder, evt_data.name))

                    # try to grab another event
                    evt_typ, evt_data = self._camera.wait_for_event(10)  # timeout in ms

                logger.info(f"got {captured_files=}")

                # now decide which file to download, we watch out for the jpg
                file_to_download = None
                for captured_file in captured_files:
                    _, file_extension = os.path.splitext(captured_file[1])  # get file extension (including .)
                    if str(file_extension).lower() in (".jpg", ".jpeg"):
                        file_to_download = captured_file

                        logger.info(f"determined {file_to_download=}")
                        break

                # check if a file was found. if no, maybe capture failed or
                if file_to_download is None:
                    logger.critical("no capture or no jpeg captured! shooting in raw-only mode?")

                    # try again in next loop
                    continue

                # read from camera
                try:
                    camera_file = self._camera.file_get(captured_file[0], captured_file[1], gp.GP_FILE_TYPE_NORMAL)
                    file_data = camera_file.get_data_and_size()
                    img_bytes = memoryview(file_data).tobytes()
                except gp.GPhoto2Error as exc:
                    logger.critical(f"error reading camera file! check logs for errors. {exc}")

                    # try again in next loop
                    continue

                # only capture one pic and return to lores streaming afterwards
                self._hires_data.request_hires_still.clear()

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
