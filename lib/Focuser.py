import os

###
# This script works after installing the driver for 16mp imx519 driver from arducam
# only driver necessary, not the libcamera apps
# How to install the driver
# https://www.arducam.com/docs/cameras-for-raspberry-pi/raspberry-pi-libcamera-guide/how-to-use-arducam-16mp-camera-on-rapberry-pi/
# You can use our auto-install script to install the driver for arducam 64MP camera:
# wget - O install_pivariety_pkgs.sh https: // github.com/ArduCAM/Arducam-Pivariety-V4L2-Driver/releases/download/install_script/install_pivariety_pkgs.sh
# chmod + x install_pivariety_pkgs.sh
# ./install_pivariety_pkgs.sh - p imx519_kernel_driver_low_speed
#
# driver may have to be reinstalled after system updates!


class Focuser:
    def __init__(self, device, CONFIG):
        self.focus_value = 0
        self._device = device
        self._CONFIG = CONFIG
        self.MAX_VALUE = self._CONFIG.FOCUSER_MAX_VALUE
        self.MIN_VALUE = self._CONFIG.FOCUSER_MIN_VALUE

        self.reset()

    def reset(self):
        self.set(self._CONFIG.FOCUSER_DEF_VALUE)

    def get(self):
        return self.focus_value

    def set(self, value):
        if value > self._CONFIG.FOCUSER_MAX_VALUE:
            value = self._CONFIG.FOCUSER_MAX_VALUE
        elif value < self._CONFIG.FOCUSER_MIN_VALUE:
            value = self._CONFIG.FOCUSER_MIN_VALUE

        value = int(value)
        os.system("v4l2-ctl -c focus_absolute={} -d {}".format(value, self._device))

        self.focus_value = value

        if self._CONFIG.DEBUG:
            print("set focus_absolute={}".format(value))


pass
