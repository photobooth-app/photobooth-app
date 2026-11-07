import logging
import os
import time
from enum import Enum
from pathlib import Path
from tempfile import NamedTemporaryFile

import gphoto2 as gp

from ...utils.helper import filename_str_time
from ..config.groups.cameras import Gphoto2Parameters, GroupCameraGphoto2
from .abstractbackend import AbstractBackend, StillRequest

logger = logging.getLogger(__name__)


class GpWidgets(Enum):
    GP_WIDGET_WINDOW = 0
    GP_WIDGET_SECTION = 1
    GP_WIDGET_TEXT = 2
    GP_WIDGET_RANGE = 3
    GP_WIDGET_TOGGLE = 4
    GP_WIDGET_RADIO = 5
    GP_WIDGET_MENU = 6
    GP_WIDGET_BUTTON = 7
    GP_WIDGET_DATE = 8


# generate dict for clear events clear text names
# defined events http://www.gphoto.org/doc/api/gphoto2-camera_8h.html#a438ab2ac60ad5d5ced30e4201476800b (docs outdated!)
class GpEvents(Enum):
    GP_EVENT_UNKNOWN = 0
    GP_EVENT_TIMEOUT = 1
    GP_EVENT_FILE_ADDED = 2
    GP_EVENT_FOLDER_ADDED = 3
    GP_EVENT_CAPTURE_COMPLETE = 4
    GP_EVENT_FILE_CHANGED = 5


# assert to ensure our definition is always the same as in libgphoto
assert {e.name: e.value for e in GpWidgets} == {name: getattr(gp, name) for name in GpWidgets.__members__}, "GP_WIDGET are inconsistent"
assert {e.name: e.value for e in GpEvents} == {name: getattr(gp, name) for name in GpEvents.__members__}, "GP_EVENT are inconsistent"


class Gphoto2Backend(AbstractBackend):
    def __init__(self, config: GroupCameraGphoto2):
        self._config: GroupCameraGphoto2 = config
        super().__init__(
            config.orientation,
            num_subdevices=1,
            idle_timeout=self._config.camera_standby_when_inactive_time if self._config.camera_standby_when_inactive else None,
        )

        if gp is None:
            raise ModuleNotFoundError("Backend is not available - either wrong platform or not installed!")

        self._camera = gp.Camera()  # pyrefly: ignore [missing-attribute]
        self._camera_context = gp.Context()

        logger.info(f"python-gphoto2: {gp.__version__}")
        logger.info(f"libgphoto2: {gp.gp_library_version(gp.GP_VERSION_VERBOSE)}")  # pyrefly: ignore [missing-attribute]
        logger.info(f"libgphoto2_port: {gp.gp_port_library_version(gp.GP_VERSION_VERBOSE)}")  # pyrefly: ignore [missing-attribute]

        # enable logging to python. need to store callback, otherwise logging does not work.
        # gphoto2 logging is too verbose, reduce mapping
        self._logger_callback = gp.check_result(
            gp.use_python_logging(
                mapping={
                    gp.GP_LOG_ERROR: logging.INFO,  # pyrefly: ignore [missing-attribute]
                    gp.GP_LOG_DEBUG: logging.DEBUG - 1,  # pyrefly: ignore [missing-attribute]
                    gp.GP_LOG_VERBOSE: logging.DEBUG - 3,  # pyrefly: ignore [missing-attribute]
                    gp.GP_LOG_DATA: logging.DEBUG - 6,  # pyrefly: ignore [missing-attribute]
                }
            )
        )

    def start(self):
        super().start()

    def stop(self):
        super().stop()

    def _handle_switchmode_init(self):
        logger.debug("configure camera during device init")
        self._handle_switchmode(self._config.parameterset_device_init)

    def _handle_switchmode_video_mode(self):
        logger.debug("configure camera optimized for video")
        self._handle_switchmode(self._config.parameterset_video)

    def _handle_switchmode_still_mode(self):
        logger.debug("configure camera optimized for still capture")
        self._handle_switchmode(self._config.parameterset_still)

    def _handle_switchmode_standby(self):
        logger.debug("configure camera optimized for standby")
        self._handle_switchmode(self._config.parameterset_standby)

    def _handle_switchmode(self, parameterset: list[Gphoto2Parameters]) -> None:
        camera_config = self._camera.get_config()

        for cfg in parameterset:
            if cfg.enabled:
                try:
                    self._update_camera_config(camera_config, cfg.name, cfg.value)
                except Exception as exc:
                    logger.warning(f"Error setting config: {exc}. It will be ignored.")

        self._camera.set_config(camera_config)  # ... and write all at once to camera

    def _update_camera_config(self, camera_config, name: str, value_new: str | int | bool | float):
        assert gp

        if name == "" or value_new == "":
            raise ValueError(f"setting is missing name '{name}' or value '{value_new}'")

        child = camera_config.get_child_by_name(name)
        is_readonly = child.get_readonly()
        typ = child.get_type()
        name = child.get_name()
        value_old = child.get_value()

        if is_readonly:
            raise PermissionError(f"'{name}' is readonly!")

        # update configuration object and properly cast the new value
        config_type = GpWidgets(typ)
        if config_type is GpWidgets.GP_WIDGET_TEXT:
            value_new_casted = str(value_new)
        elif config_type in (GpWidgets.GP_WIDGET_RADIO, GpWidgets.GP_WIDGET_MENU):
            # radio/menu widgets allow only specific values, so it allows to validate the user provided data before it's sent
            # to the camera and breaks everything. The available choices reported by the camera may differ by the selected mode
            available_choices = [choice for choice in child.get_choices()]

            if value_new not in available_choices:
                raise ValueError(f"{value_new} is not an option for '{name}' in current mode. Available choices are {available_choices}")

            value_new_casted = str(value_new)
        elif config_type is GpWidgets.GP_WIDGET_TOGGLE:
            value_new_casted = 1 if str(value_new).lower() in ("true", "1") else 0
        else:
            raise RuntimeError(f"The app does not support the setting's type '{config_type}' for {child.get_name()}")

        try:
            child.set_value(value_new_casted)  # update the python object ...
            logger.debug(f"Camera setting '{name}' changed from '{value_old}' to '{value_new}' ({value_new_casted})")
        except Exception as exc:
            logger.exception(exc)
            raise RuntimeError(f"Cannot set '{name}' to '{value_new}'! Command ignored. Error: {exc}") from exc

    def setup_resource(self):
        assert gp

        # try open cam. if fails it raises an exception and the supvervisor tries to restart.
        # better use fresh object.
        self._camera = gp.Camera()  # pyrefly: ignore [missing-attribute]
        try:
            self._camera.init()  # if init was success, the backend is ready to deliver, no additional later checks needed.
        except gp.GPhoto2Error as exc:
            # logger.error(f"could not get camera information, error {exc}")
            logger.debug("error occured, please check https://photobooth-app.org/help/faq/#gphoto2-camera-found-but-no-access for troubleshooting.")
            raise ConnectionError(f"Could not connect to camera, error: {exc}") from exc

    def display_config(self, camera_config):
        for child in camera_config:
            # label = f"{child.get_label()} ({child.get_name()}=({child.get_value()}))"
            if GpWidgets(child.get_type()) == GpWidgets.GP_WIDGET_SECTION:
                print("\n\n- SECTION: ", end="")
                print(f"{child.get_label()} ({child.get_name()})")

                self.display_config(child)
            else:
                print(f"{child.get_name()}='{child.get_value()}'   {child.get_label()}   {' (readonly) ' if child.get_readonly() else ''}  ")
                print(f"type={GpWidgets(child.get_type()).name}")
                if GpWidgets(child.get_type()) in (GpWidgets.GP_WIDGET_RADIO, GpWidgets.GP_WIDGET_MENU):
                    print(f"available options {{index, value}} are {[{idx: choice} for idx, choice in enumerate(child.get_choices())]}")
                print()

    def teardown_resource(self):
        if self._camera:
            self._camera.exit()

    def run_service(self):
        assert gp

        preview_failcounter = 0

        while not self._stop_event.is_set():  # repeat until stopped
            with self._hires_lock:
                req = self._hires_queue.popleft() if self._hires_queue else None

            if req:
                if isinstance(req, StillRequest):
                    # capture hq picture
                    logger.info("taking hq picture")

                    # hold a list of captured files during capture. this is needed if JPG+RAW is shot.
                    # there is no guarantee that the first is the JPG and second the RAW image. Also depending on the capturetarget
                    # the sequence the images appear can be different. gp.GP_CAPTURE_IMAGE vs gp.GP_CAPTURE_RAW seems not reliable to rely on
                    captured_files: list[tuple[str, str]] = []

                    with self._mode_machine.ext_mode_switch_lock:
                        # we force the camera to still mode and do not allow to change the mode until it is completed.
                        # otherwise the app could request
                        self._mode_machine.process_switchmode("still")

                        try:
                            self._camera.trigger_capture()
                        except gp.GPhoto2Error as exc:
                            logger.critical(f"error capture! check logs for errors. {exc}")

                            # try again in next loop
                            time.sleep(0.6)  # if it fails before next round, wait little because it might fail fast again
                            continue

                    # empty the event queue, needed in case of RAW+JPG shooting usually.
                    # used usually only if capture JPG+RAW enabled (2 files added in one capture)
                    # if not cleared, the second capture might fail due to pending events in libgphoto2
                    # also if raw, we might have the JPG added later in these events, not received from .capture above
                    # https://github.com/jim-easterbrook/python-gphoto2/issues/65#issuecomment-433615025
                    while True:
                        evt_typ_cam, evt_data_cam = self._camera.wait_for_event(2000)
                        evt_typ = GpEvents(evt_typ_cam)

                        if evt_typ in (GpEvents.GP_EVENT_CAPTURE_COMPLETE, GpEvents.GP_EVENT_TIMEOUT):
                            logger.debug(f"Event '{evt_typ.name}' received, capture is complete, continue to download capture.")
                            break
                        elif evt_typ is GpEvents.GP_EVENT_FILE_ADDED:
                            logger.debug(f"Event '{evt_typ.name}' received', event data is '{evt_data_cam}'")
                            captured_files.append((evt_data_cam.folder, evt_data_cam.name))
                        else:
                            logger.debug(f"Event '{evt_typ.name}' received', event data is '{evt_data_cam}'")

                    logger.info(f"got {captured_files=}")

                    # now decide which file to download, we watch out for the jpg
                    file_to_download = None
                    for captured_file in captured_files:
                        _, file_extension = os.path.splitext(captured_file[1])  # get file extension (including .)
                        if file_extension.lower() in (".jpg", ".jpeg"):
                            file_to_download = captured_file

                            logger.info(f"determined {file_to_download=}")
                            break

                    # check if a file was found. if no, maybe capture failed or
                    if file_to_download is None:
                        logger.critical("no capture or no jpeg captured! shooting in raw-only mode?")

                        # try again in next loop
                        time.sleep(0.6)  # if it fails before next round, wait little because it might fail fast again
                        continue

                    # read from camera
                    try:
                        # only capture one pic and return to lores streaming afterwards
                        filepath = Path(
                            NamedTemporaryFile(
                                mode="wb",
                                delete=False,
                                dir="tmp",
                                prefix=f"{filename_str_time()}_gphoto2_",
                                suffix=".jpg",
                            ).name
                        )

                        camera_file = self._camera.file_get(file_to_download[0], file_to_download[1], gp.GP_FILE_TYPE_NORMAL)  # pyrefly: ignore [missing-attribute]
                        camera_file.save(str(filepath))

                    except gp.GPhoto2Error as exc:
                        logger.critical(f"error reading camera file! check logs for errors. {exc}")

                        # try again in next loop
                        time.sleep(0.6)  # if it fails before next round, wait little because it might fail fast again
                        continue

                    with req.condition:
                        req.result_file = filepath
                        req.condition.notify_all()
                else:
                    logger.warning(f"this backend does not support {type(req)} requests")
                    continue
            else:
                # lores/preview stream

                self._mode_machine.process_switchmode()

                if self._mode_machine.active_mode == "standby":
                    time.sleep(0.2)
                    continue

                # Pi5 seems too fast for the old fashioned gphoto lib, permanently producing
                # (ptp_usb_getresp [usb.c:516]) PTP_OC 0x9153 receiving resp failed: Camera Not Ready (0xa102) (port_log.py:20)
                # in the logs. to avoid that, we just sleep a bit here effectively frame limiting and
                # giving gphoto2 time to settle and avoid flooded logs.
                self._framerate.wait_until_fps(25)

                try:
                    camera_file = self._camera.capture_preview()
                    self._frame_tick()
                    img_bytes = memoryview(camera_file.get_data_and_size()).tobytes()

                    with self._lores_data[0].condition:
                        self._lores_data[0].data = img_bytes
                        self._lores_data[0].condition.notify_all()

                except Exception as exc:
                    preview_failcounter += 1

                    if preview_failcounter <= 10:
                        logger.warning(f"error capturing frame from DSLR: {exc}")
                        # abort this loop iteration and continue sleeping...
                        time.sleep(0.5)  # add another delay to avoid flooding logs

                        continue
                    else:
                        logger.critical(f"aborting capturing frame, camera disconnected? retry to connect {exc}")
                        try:
                            self._camera.exit()
                        except Exception:
                            pass  # fail in silence, because things got already wrong. this one is just to try to cleanup, might help or not...

                        # stop device requested by leaving worker loop, so supvervisor can restart
                        raise RuntimeError(f"Error communicating with the camera: {exc}") from exc
                else:
                    preview_failcounter = 0
