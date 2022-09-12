import time
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


def init(bus, address):
    return


def write(bus, address, value):
    os.system("v4l2-ctl -c focus_absolute={} -d {}".format(value, bus))


class Focuser:
    bus = None
    CHIP_I2C_ADDR = 0x0C

    def __init__(self, bus):
        self.focus_value = 0
        self.bus = bus
        self.verbose = False
        init(self.bus, self.CHIP_I2C_ADDR)

    def read(self):
        return self.focus_value

    def write(self, chip_addr, value):
        if value < 0:
            value = 0
        self.focus_value = value

        value = int(value)

        write(self.bus, chip_addr, value)

    OPT_BASE = 0x1000
    OPT_FOCUS = OPT_BASE | 0x01
    OPT_ZOOM = OPT_BASE | 0x02
    OPT_MOTOR_X = OPT_BASE | 0x03
    OPT_MOTOR_Y = OPT_BASE | 0x04
    OPT_IRCUT = OPT_BASE | 0x05
    opts = {
        OPT_FOCUS: {
            "MIN_VALUE": 0,
            "MAX_VALUE": 4000,
            "DEF_VALUE": 400,
        },
    }

    def reset(self, opt, flag=1):
        info = self.opts[opt]
        if info == None or info["DEF_VALUE"] == None:
            return
        self.set(opt, info["DEF_VALUE"])

    def get(self, opt, flag=0):
        info = self.opts[opt]
        return self.read()

    def set(self, opt, value, flag=1):
        info = self.opts[opt]
        if value > info["MAX_VALUE"]:
            value = info["MAX_VALUE"]
        elif value < info["MIN_VALUE"]:
            value = info["MIN_VALUE"]
        self.write(self.CHIP_I2C_ADDR, value)
        if self.verbose:
            print("set focus_absolute={}".format(value))


pass


def test():
    focuser = Focuser(7)
    focuser.set(Focuser.OPT_FOCUS, 0)
    time.sleep(3)
    focuser.set(Focuser.OPT_FOCUS, 1000)
    time.sleep(3)
    focuser.reset(Focuser.OPT_FOCUS)


if __name__ == "__main__":
    test()
