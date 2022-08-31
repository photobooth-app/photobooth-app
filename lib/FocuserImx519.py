import time
import os


def init(bus, address):
    return


def write(bus, address, value):
    os.system("v4l2-ctl -c focus_absolute={} -d {}".format(value, bus))


class Focuser519:
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
            "DEF_VALUE": 0,
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
    focuser = Focuser519(7)
    focuser.set(Focuser519.OPT_FOCUS, 0)
    time.sleep(3)
    focuser.set(Focuser519.OPT_FOCUS, 1000)
    time.sleep(3)
    focuser.reset(Focuser519.OPT_FOCUS)


if __name__ == "__main__":
    test()
