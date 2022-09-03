try:
    import v4l2
except Exception as e:
    print(e)
    print("Try to install v4l2-fix")
    try:
        from pip import main as pipmain
    except ImportError:
        from pip._internal import main as pipmain
    pipmain(['install', 'v4l2-fix'])
    print("\nTry to run the focus program again.")
    exit(0)

import fcntl
import errno

# # Type
# v4l2.V4L2_CTRL_TYPE_INTEGER
# v4l2.V4L2_CTRL_TYPE_BOOLEAN
# v4l2.V4L2_CTRL_TYPE_MENU
# v4l2.V4L2_CTRL_TYPE_BUTTON
# v4l2.V4L2_CTRL_TYPE_INTEGER64
# v4l2.V4L2_CTRL_TYPE_CTRL_CLASS
# # Flags
# v4l2.V4L2_CTRL_FLAG_DISABLED
# v4l2.V4L2_CTRL_FLAG_GRABBED
# v4l2.V4L2_CTRL_FLAG_READ_ONLY
# v4l2.V4L2_CTRL_FLAG_UPDATE
# v4l2.V4L2_CTRL_FLAG_INACTIVE
# v4l2.V4L2_CTRL_FLAG_SLIDER

def assert_valid_queryctrl(queryctrl):
    return queryctrl.type & (
        v4l2.V4L2_CTRL_TYPE_INTEGER
        | v4l2.V4L2_CTRL_TYPE_BOOLEAN
        | v4l2.V4L2_CTRL_TYPE_MENU
        | v4l2.V4L2_CTRL_TYPE_BUTTON
        | v4l2.V4L2_CTRL_TYPE_INTEGER64
        | v4l2.V4L2_CTRL_TYPE_CTRL_CLASS
        | 7
        | 8
        | 9
    ) and queryctrl.flags & (
        v4l2.V4L2_CTRL_FLAG_DISABLED
        | v4l2.V4L2_CTRL_FLAG_GRABBED
        | v4l2.V4L2_CTRL_FLAG_READ_ONLY
        | v4l2.V4L2_CTRL_FLAG_UPDATE
        | v4l2.V4L2_CTRL_FLAG_INACTIVE
        | v4l2.V4L2_CTRL_FLAG_SLIDER
    )

def get_device_controls_menu(fd, queryctrl):
    querymenu = v4l2.v4l2_querymenu(queryctrl.id, queryctrl.minimum)
    while querymenu.index <= queryctrl.maximum:
        fcntl.ioctl(fd, v4l2.VIDIOC_QUERYMENU, querymenu)
        yield querymenu
        querymenu.index += 1

def get_device_controls_by_class(fd, control_class):
    # enumeration by control class
    queryctrl = v4l2.v4l2_queryctrl(control_class | v4l2.V4L2_CTRL_FLAG_NEXT_CTRL)
    while True:
        try:
            fcntl.ioctl(fd, v4l2.VIDIOC_QUERYCTRL, queryctrl)
        except IOError as e:
            assert e.errno == errno.EINVAL
            break
        if v4l2.V4L2_CTRL_ID2CLASS(queryctrl.id) != control_class:
            break
        yield queryctrl
        queryctrl = v4l2.v4l2_queryctrl(queryctrl.id | v4l2.V4L2_CTRL_FLAG_NEXT_CTRL)

def getdict(struct):
    val = dict((field, getattr(struct, field)) for field, _ in struct._fields_)
    val.pop("reserved")
    return val

def get_device_controls(fd):
    # original enumeration method
    queryctrl = v4l2.v4l2_queryctrl(v4l2.V4L2_CID_BASE)
    while queryctrl.id < v4l2.V4L2_CID_LASTP1:
        try:
            fcntl.ioctl(fd, v4l2.VIDIOC_QUERYCTRL, queryctrl)
            print(queryctrl.name)
        except IOError as e:
            # this predefined control is not supported by this device
            assert e.errno == errno.EINVAL
            queryctrl.id += 1
            continue
        queryctrl = v4l2.v4l2_queryctrl(queryctrl.id + 1)

def get_ctrls(vd):
    ctrls = []
    # enumeration by control class
    for class_ in (v4l2.V4L2_CTRL_CLASS_USER, v4l2.V4L2_CTRL_CLASS_MPEG, v4l2.V4L2_CTRL_CLASS_CAMERA):
        for queryctrl in get_device_controls_by_class(vd, class_):
            ctrl = getdict(queryctrl)
            if queryctrl.type == v4l2.V4L2_CTRL_TYPE_MENU:
                ctrl["menu"] = []
                for querymenu in get_device_controls_menu(vd, queryctrl):
                    # print(querymenu.name)
                    ctrl["menu"].append(querymenu.name)

            if queryctrl.type == 9:
                ctrl["menu"] = []
                for querymenu in get_device_controls_menu(vd, queryctrl):
                    ctrl["menu"].append(querymenu.index)
            ctrls.append(ctrl)
    return ctrls

def set_ctrl(vd, id, value):
    ctrl = v4l2.v4l2_control()
    ctrl.id = id
    ctrl.value = value
    try:
        fcntl.ioctl(vd, v4l2.VIDIOC_S_CTRL, ctrl)
    except IOError as e:
        print(e)

def get_ctrl(vd, id):
    ctrl = v4l2.v4l2_control()
    ctrl.id = id
    try:
        fcntl.ioctl(vd, v4l2.VIDIOC_G_CTRL, ctrl)
    except IOError as e:
        print(e)
        return None
    return ctrl.value


if __name__ == "__main__":
    vd = open("/dev/video0", 'r')
    ctrls = get_ctrls(vd)
    # set_ctrl(vd, ctrls[1]["id"], 100)
    for ctrl in ctrls:
        print(ctrl)
