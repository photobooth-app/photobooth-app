import os
import logging
from ConfigSettings import settings

logger = logging.getLogger(__name__)


class ImageServerAddonAutofocusFocuser:
    """
    This script works after installing the driver for 16mp imx519 driver from arducam
    only driver necessary, not the libcamera apps
    How to install the driver
    https://www.arducam.com/docs/cameras-for-raspberry-pi/raspberry-pi-libcamera-guide/how-to-use-arducam-16mp-camera-on-rapberry-pi/
    You can use our auto-install script to install the driver for arducam 64MP camera:
    wget - O install_pivariety_pkgs.sh https: // github.com/ArduCAM/Arducam-Pivariety-V4L2-Driver/releases/download/install_script/install_pivariety_pkgs.sh
    chmod + x install_pivariety_pkgs.sh
    ./install_pivariety_pkgs.sh - p imx519_kernel_driver_low_speed
    driver may have to be reinstalled after system updates!
    """

    def __init__(self):
        self.focus_value = 0
        self._device = settings.common.FOCUSER_DEVICE
        self.MAX_VALUE = settings.common.FOCUSER_MAX_VALUE
        self.MIN_VALUE = settings.common.FOCUSER_MIN_VALUE

        self.reset()

    def reset(self):
        self.set(settings.common.FOCUSER_DEF_VALUE)

    def get(self):
        return self.focus_value

    def set(self, value):
        if value > settings.common.FOCUSER_MAX_VALUE:
            value = settings.common.FOCUSER_MAX_VALUE
        elif value < settings.common.FOCUSER_MIN_VALUE:
            value = settings.common.FOCUSER_MIN_VALUE

        value = int(value)
        try:
            os.system(
                "v4l2-ctl -c focus_absolute={} -d {}".format(value, self._device))
        except Exception as e:
            logger.exception(e)
            logger.error(f"Error on focus command: {e}")

        self.focus_value = value
