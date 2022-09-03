'''
    Arducam programable focus control component.

    Copyright (c) 2020-5 Arducam <http://www.arducam.com>.

    Permission is hereby granted, free of charge, to any person obtaining a copy
    of this software and associated documentation files (the "Software"), to deal
    in the Software without restriction, including without limitation the rights
    to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
    copies of the Software, and to permit persons to whom the Software is
    furnished to do so, subject to the following conditions:

    The above copyright notice and this permission notice shall be included in all
    copies or substantial portions of the Software.

    THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
    EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
    MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
    IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM,
    DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR
    OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE
    OR OTHER DEALINGS IN THE SOFTWARE.
'''

import v4l2_utils
import time


class Focuser:
    FOCUS_ID = 0x009a090a
    dev = None

    def __init__(self, dev=0):
        self.focus_value = 0
        self.dev = dev

        if type(dev) == int or (type(dev) == str and dev.isnumeric()):
            self.dev = "/dev/video{}".format(dev)

        self.fd = open(self.dev, 'r')
        self.ctrls = v4l2_utils.get_ctrls(self.fd)
        print(self.ctrls)
        self.hasFocus = False
        for ctrl in self.ctrls:
            if ctrl['id'] == Focuser.FOCUS_ID:
                self.hasFocus = True
                self.opts[Focuser.OPT_FOCUS]["MIN_VALUE"] = ctrl['minimum']
                self.opts[Focuser.OPT_FOCUS]["MAX_VALUE"] = ctrl['maximum']
                if hasattr(ctrl, 'default'):
                    self.opts[Focuser.OPT_FOCUS]["DEF_VALUE"] = ctrl['default']
                if hasattr(ctrl, 'default_value'):
                    self.opts[Focuser.OPT_FOCUS]["DEF_VALUE"] = ctrl['default_value']
                self.focus_value = v4l2_utils.get_ctrl(
                    self.fd, Focuser.FOCUS_ID)

        if not self.hasFocus:
            raise RuntimeError(
                "Device {} has no focus_absolute control.".format(self.dev))

    def read(self):
        return self.focus_value

    def write(self, value):
        self.focus_value = value
        # os.system("v4l2-ctl -d {} -c focus_absolute={}".format(self.dev, value))
        v4l2_utils.set_ctrl(self.fd, Focuser.FOCUS_ID, value)

    OPT_BASE = 0x1000
    OPT_FOCUS = OPT_BASE | 0x01
    OPT_ZOOM = OPT_BASE | 0x02
    OPT_MOTOR_X = OPT_BASE | 0x03
    OPT_MOTOR_Y = OPT_BASE | 0x04
    OPT_IRCUT = OPT_BASE | 0x05
    opts = {
        OPT_FOCUS: {
            "MIN_VALUE": 0,
            "MAX_VALUE": 1000,
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
        self.write(value)
        print("write: {}".format(value))

    def __del__(self):
        self.fd.close()


pass


def test():
    focuser = Focuser(0)
    focuser.set(Focuser.OPT_FOCUS, 0)
    time.sleep(3)
    focuser.set(Focuser.OPT_FOCUS, 1000)
    time.sleep(3)
    focuser.reset(Focuser.OPT_FOCUS)


if __name__ == "__main__":
    test()
