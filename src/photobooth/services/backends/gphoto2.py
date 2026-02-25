"""
Gphoto2 backend implementation

"""

import logging
import os
import time
from pathlib import Path
from tempfile import NamedTemporaryFile

from ...utils.helper import filename_str_time
from ..config.groups.cameras import GroupCameraGphoto2
from .abstractbackend import AbstractBackend, StillRequest

try:
    import gphoto2 as gp  # type: ignore
except ImportError:
    gp = None

logger = logging.getLogger(__name__)


class Gphoto2Backend(AbstractBackend):
    def __init__(self, config: GroupCameraGphoto2):
        self._config: GroupCameraGphoto2 = config
        super().__init__(config.orientation, num_subdevices=1)

        if gp is None:
            raise ModuleNotFoundError("Backend is not available - either wrong platform or not installed!")

        self._camera = gp.Camera()  # pyright: ignore [reportAttributeAccessIssue]
        self._camera_context = gp.Context()  # pyright: ignore [reportAttributeAccessIssue]

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

        logger.info(f"python-gphoto2: {gp.__version__}")
        logger.info(f"libgphoto2: {gp.gp_library_version(gp.GP_VERSION_VERBOSE)}")  # pyright: ignore [reportAttributeAccessIssue]
        logger.info(f"libgphoto2_port: {gp.gp_port_library_version(gp.GP_VERSION_VERBOSE)}")  # pyright: ignore [reportAttributeAccessIssue]

        # enable logging to python. need to store callback, otherwise logging does not work.
        # gphoto2 logging is too verbose, reduce mapping
        self._logger_callback = gp.check_result(
            gp.use_python_logging(
                mapping={
                    gp.GP_LOG_ERROR: logging.INFO,  # pyright: ignore [reportAttributeAccessIssue]
                    gp.GP_LOG_DEBUG: logging.DEBUG - 1,  # pyright: ignore [reportAttributeAccessIssue]
                    gp.GP_LOG_VERBOSE: logging.DEBUG - 3,  # pyright: ignore [reportAttributeAccessIssue]
                    gp.GP_LOG_DATA: logging.DEBUG - 6,  # pyright: ignore [reportAttributeAccessIssue]
                }
            )
        )

    def start(self):
        super().start()

    def stop(self):
        super().stop()

    def _handle_switchmode_video_mode(self):
        # idle and hq_preview are same settings for this backend.
        logger.debug("configure camera optimized for idle/video")

        self._set_config("iso", self._config.iso_liveview)
        self._set_config("shutterspeed", self._config.shutter_speed_liveview)

        if self._config.canon_eosmoviemode:
            self._set_config("eosmoviemode", 1)
        super()._handle_switchmode_video_mode()

    def _handle_switchmode_still_mode(self):
        logger.debug("configure camera optimized for still capture")

        # disable viewfinder;
        # allows camera to autofocus fast in native mode not contrast mode
        if self._config.disable_viewfinder_before_capture:
            logger.info("disable viewfinder before capture")
            self._set_config("viewfinder", 0)

        self._set_config("iso", self._config.iso_capture)
        self._set_config("shutterspeed", self._config.shutter_speed_capture)

        if self._config.canon_eosmoviemode:
            self._set_config("eosmoviemode", 0)

        super()._handle_switchmode_still_mode()

    def _handle_switchmode_standby(self):
        logger.debug("configure camera optimized for livestream paused")

        # pause is to stop streaming from the camera to avoid overheating of the sensor
        # this is an internal event so no flag reset, it's handled differently

        # disable viewfinder;
        self._set_config("viewfinder", 0)

        if self._config.canon_eosmoviemode:
            self._set_config("eosmoviemode", 0)

        super()._handle_switchmode_standby()

    def _set_config(self, field: str, val: str | int = ""):
        assert gp

        if val == "":  # 0 is not considered empty, so its not "not val"
            logger.debug(f"{field} value empty, ignore")
            return
        try:
            logger.info(f"setting {field} to {val}")
            self._gp_set_config(field, val)
        except gp.GPhoto2Error as exc:
            logger.warning(f"cannot set {field} to {val}, command ignored {exc}")
        except AttributeError as exc:
            logger.info(f"cannot set config because camera is not yet available, error {exc}")

    def _gp_set_config(self, name, val):
        config = self._camera.get_config(self._camera_context)
        node = config.get_child_by_name(name)
        node.set_value(val)
        self._camera.set_config(config, self._camera_context)

    def setup_resource(self):
        assert gp

        # try open cam. if fails it raises an exception and the supvervisor tries to restart.
        # better use fresh object.
        self._camera = gp.Camera()  # pyright: ignore [reportAttributeAccessIssue]
        try:
            self._camera.init()  # if init was success, the backend is ready to deliver, no additional later checks needed.
        except gp.GPhoto2Error as exc:
            # logger.error(f"could not get camera information, error {exc}")
            logger.debug("error occured, please check https://photobooth-app.org/help/faq/#gphoto2-camera-found-but-no-access for troubleshooting.")
            raise ConnectionError(f"Could not connect to camera, error: {exc}") from exc

        try:
            logger.info(str(self._camera.get_summary()))
        except gp.GPhoto2Error as exc:
            logger.error(f"could not get camera information, error {exc}")

        if "PYTEST_CURRENT_TEST" in os.environ:
            # https://github.com/jim-easterbrook/python-gphoto2/issues/192#issuecomment-3055702591
            if gp.gp_library_version(gp.GP_VERSION_SHORT)[0] == "2.5.32":  # pyright: ignore [reportAttributeAccessIssue]
                logger.warning("temporary fix for gphoto lib 2.5.32; remove once new version is released.")
                # workaround for https://github.com/gphoto/libgphoto2/issues/1136
                self._camera.folder_list_folders("/store_00010001")

        self._set_config("capturetarget", self._config.gcapture_target)

    def teardown_resource(self):
        if self._camera:
            self._camera.exit()

    def run_service(self):
        assert gp

        preview_failcounter = 0
        self._handle_switchmode_video_mode()

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

                    # check if flag is true and configure if so once.
                    self._mode_machine.ensure_still_mode()

                    try:
                        file_path = self._camera.capture(gp.GP_CAPTURE_IMAGE)  # pyright: ignore [reportAttributeAccessIssue]
                        captured_files.append((file_path.folder, file_path.name))
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
                    evt_typ, evt_data = self._camera.wait_for_event(200)
                    while evt_typ != gp.GP_EVENT_TIMEOUT:  # pyright: ignore [reportAttributeAccessIssue]
                        logger.debug(f"Event: {self.event_texts.get(evt_typ, f'unknown event index: {evt_typ}')}, data: {evt_data}")

                        if evt_typ == gp.GP_EVENT_FILE_ADDED:  # pyright: ignore [reportAttributeAccessIssue]
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

                        camera_file = self._camera.file_get(file_to_download[0], file_to_download[1], gp.GP_FILE_TYPE_NORMAL)  # pyright: ignore [reportAttributeAccessIssue]
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

                if self._mode_machine.standby.is_active:  # type: ignore
                    time.sleep(0.1)
                    continue

                self._mode_machine.ensure_video_mode()

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
                        except Exception as exc:
                            pass  # fail in silence, because things got already wrong. this one is just to try to cleanup, might help or not...

                        # stop device requested by leaving worker loop, so supvervisor can restart
                        break
                else:
                    preview_failcounter = 0
