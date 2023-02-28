"""
custom autofocus module mainly used for arducams
"""
import os
import json
import threading
import time
import logging
from queue import Queue

try:
    from smbus import SMBus
except ImportError as import_exc:
    raise OSError("smbus not supported on windows platform") from import_exc
from turbojpeg import TurboJPEG
from pymitter import EventEmitter
from src.configsettings import settings
from src.imageserverabstract import ImageServerAbstract
from src.repeatedtimer import RepeatedTimer

logger = logging.getLogger(__name__)


class ImageServerPicam2AddonCustomAutofocus:
    """
    Class implementing custom autofocuser for arducam cameras
    """

    def __init__(self, imageserver: ImageServerAbstract, evtbus: EventEmitter):
        self._imageserver: ImageServerAbstract = imageserver
        self._evtbus = evtbus
        self._evtbus.on("onRefocus", self.do_focus)
        self._evtbus.on("statemachine/armed", self.set_ignore_focus_requests)
        self._evtbus.on("statemachine/finished", self.set_allow_focus_requests)
        self._evtbus.on("onCaptureMode", self.set_ignore_focus_requests)
        self._evtbus.on("onPreviewMode", self.set_allow_focus_requests)

        self._last_run_result = []
        self._last_final_position = settings.focuser.DEF_VALUE
        self.sharpness_list = Queue()
        self.lock = threading.Lock()
        self.direction = 1
        self.finish = True
        self._standby = False

        self.set_allow_focus_requests()
        self.reset()

        self._rt = RepeatedTimer(
            settings.focuser.REPEAT_TRIGGER, self.trigger_regular_timed_focus
        )

        self.start_regular_autofocus_timer()

    def start_regular_autofocus_timer(self):
        """_summary_"""
        self._rt.start()

    def stop_regular_autofocus_timer(self):
        """_summary_"""
        self._rt.stop()

    def abort_ongoing_focus_thread(self):
        """_summary_"""
        logger.debug("abort ongoing focus thread")
        self.set_finish(True)

    def set_ignore_focus_requests(self):
        """_summary_"""
        self._standby = True

    def set_allow_focus_requests(self):
        """_summary_"""
        self._standby = False

    def trigger_regular_timed_focus(self):
        """_summary_"""
        if not self._standby:
            self.do_focus()

    def do_focus(self):
        """_summary_"""
        # guard to perfom autofocus only once at a time
        if self.is_finish() and self._standby is False and settings.focuser.ENABLED:
            self.reset()
            self.set_finish(False)

            thread_autofocus_stats = threading.Thread(
                name="AutofocusStats",
                target=stats_thread,
                args=(self._imageserver, self),
                daemon=True,
            )
            thread_autofocus_stats.start()

            thread_autofocus_focussupervisor = threading.Thread(
                name="AutofocusSupervisor",
                target=focus_thread,
                args=(self,),
                daemon=True,
            )
            thread_autofocus_focussupervisor.start()

        else:
            logger.warning("Focus is not done yet or in standby.")

    def is_finish(self):
        """_summary_

        Returns:
            _type_: _description_
        """
        with self.lock:
            finish = self.finish

        return finish

    def set_finish(self, finish=True):
        """_summary_

        Args:
            finish (bool, optional): _description_. Defaults to True.
        """
        with self.lock:
            self.finish = finish

    def reset(self):
        """_summary_"""
        self.sharpness_list = Queue()
        self.set_finish(True)


def get_roi_frame(roi, frame):
    """_summary_

    Args:
        roi (_type_): _description_
        frame (_type_): _description_

    Returns:
        _type_: _description_
    """
    height, width = frame.shape[:2]
    x_start = int(width * roi[0])
    x_end = x_start + int(width * roi[2])

    y_start = int(height * roi[1])
    y_end = y_start + int(height * roi[3])

    roi_frame = frame[y_start:y_end, x_start:x_end]

    return roi_frame


def stats_thread(
    imageserver: ImageServerAbstract,
    imageserver_addon_customautofocus: ImageServerPicam2AddonCustomAutofocus,
):
    """_summary_

    Args:
        imageserver (ImageServerAbstract): _description_
        imageserver_addon_customautofocus (ImageServerPicam2AddonCustomAutofocus): _description_
    """
    max_position = settings.focuser.MAX_VALUE
    min_position = settings.focuser.MIN_VALUE
    last_position = imageserver_addon_customautofocus._last_final_position

    jpeg = TurboJPEG()
    last_time = time.time()
    skipped_frame_counter = 0
    sharpness_list = []

    while not imageserver_addon_customautofocus.is_finish():
        try:
            frame = imageserver._wait_for_lores_frame()
        except NotImplementedError:
            logger.error(
                "imageserver backend not to deliver frames for autofocus - disable autofocus"
            )
            imageserver_addon_customautofocus.stop_regular_autofocus_timer()
            imageserver_addon_customautofocus.reset()
            break
        except IOError:
            logger.warning("imageserver did not deliver frames, aborting cycle")
            imageserver_addon_customautofocus.stop_regular_autofocus_timer()
            imageserver_addon_customautofocus.reset()
            break

        if (
            time.time() - last_time >= settings.focuser.MOVE_TIME
            and not imageserver_addon_customautofocus.is_finish()
        ):
            last_time = time.time()

            next_position = last_position + (
                imageserver_addon_customautofocus.direction * settings.focuser.STEP
            )

            if next_position < max_position and next_position > min_position:
                set_focus_position(next_position)

            # calc window x, y, width, height
            roi = (
                settings.focuser.ROI / 100,
                (settings.focuser.ROI / 100),
                (
                    1 - (2 * settings.focuser.ROI / 100),
                    1 - (2 * settings.focuser.ROI / 100),
                ),
            )
            roi_frame = get_roi_frame(roi, frame)
            buffer = jpeg.encode(roi_frame, quality=80)

            # frame is a jpeg; len is the size of the jpeg.
            # the more contrast, the sharper the picture is and thus the bigger the size.
            sharpness = len(buffer)
            item = (last_position, sharpness)
            sharpness_list.append(item)
            imageserver_addon_customautofocus.sharpness_list.put(item)

            last_position += (
                imageserver_addon_customautofocus.direction * settings.focuser.STEP
            )

            if last_position > max_position:
                break

            if last_position < min_position:
                break
        else:
            # Focus motor cannot catch up with camera fps. This is not a problem actually.
            skipped_frame_counter += 1

    # End of stats.
    imageserver_addon_customautofocus.sharpness_list.put((-1, -1))
    imageserver_addon_customautofocus._last_run_result = sharpness_list

    # reverse search direction next time.
    imageserver_addon_customautofocus.direction *= -1

    imageserver_addon_customautofocus._evtbus.emit(
        "publishSSE",
        sse_event="autofocus/sharpness",
        sse_data=json.dumps(sharpness_list),
    )

    logger.debug(f"autofocus run finished, sharpnessList={sharpness_list}")
    if skipped_frame_counter:
        logger.debug(
            f"skipped {skipped_frame_counter} frames because motor "
            f"cannot catch up with FPS of camera. not a problem, could be tuned."
        )


def focus_thread(
    imageserver_addon_customautofocus: ImageServerPicam2AddonCustomAutofocus,
):
    """_summary_

    Args:
        imageserver_addon_customautofocus (ImageServerPicam2AddonCustomAutofocus): _description_
    """
    sharpness_list = []
    continuousdecline_req = 6
    continuousdecline = 0
    max_position = 0
    last_sharpness = 0
    while not imageserver_addon_customautofocus.is_finish():
        position, sharpness = imageserver_addon_customautofocus.sharpness_list.get()

        if last_sharpness / sharpness >= 1:
            continuousdecline += 1
        else:
            continuousdecline = 0
            max_position = position

        last_sharpness = sharpness

        if continuousdecline >= continuousdecline_req:
            imageserver_addon_customautofocus.set_finish()

        if position == -1 and sharpness == -1:
            break

        sharpness_list.append((position, sharpness))

    # Mark to finish.
    imageserver_addon_customautofocus.set_finish()

    max_item = max(sharpness_list, key=lambda item: item[1])

    logger.debug(f"max: {max_item}")

    if continuousdecline < continuousdecline_req:
        set_focus_position(max_item[0])
        imageserver_addon_customautofocus._last_final_position = max_item[0]
    else:
        set_focus_position(max_position)
        imageserver_addon_customautofocus._last_final_position = max_position


def set_focus_position(position):
    """_summary_

    Args:
        position (_type_): _description_

    Raises:
        ValueError: _description_
    """
    value = int(position)
    try:
        focuser = settings.focuser.focuser_backend.value
        if focuser == "arducam_imx477":
            arducam_imx477_focuser(value)
        elif focuser == "arducam_imx519":
            arducam_imx519_64mp_focuser(value)
        elif focuser == "arducam_64mp":
            arducam_imx519_64mp_focuser(value)
        else:
            raise ValueError("invalid focuser model selected")

    except Exception as exc:
        logger.exception(exc)
        logger.error(f"Error on focus command: {exc}")


def arducam_imx477_focuser(position):
    """_summary_

    Args:
        position (_type_): _description_
    """
    bus = 10
    i2caddress = 0x0C

    value = (position << 4) & 0x3FF0
    dat1 = (value >> 8) & 0x3F
    dat2 = value & 0xF0

    i2cbus = SMBus(bus)
    i2cbus.write_byte_data(i2caddress, dat1, dat2)

    # i2c bus above same as in arducam libs:
    # os.system("i2cset -y %d 0x0c %d %d" % (bus, dat1, dat2))


def arducam_imx519_64mp_focuser(position):
    """_summary_

    Args:
        position (_type_): _description_
    """
    os.system(f"v4l2-ctl -c focus_absolute={position} -d /dev/v4l-subdev1")
