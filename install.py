import os.path
import os
import ctypes
import sys
import subprocess
import platform
from pathlib import Path

MIN_PYTHON_VERSION = (3, 9)

if os.path.isfile("imageserver.py"):
    # if imageserver.py is detected, assume the sourcecode was already copied to target computer
    # useful if just want to enable service, install desktop shortcut, ...
    INSTALL_DIR = './'
    SUPPRESS_INSTALLATION = True
else:
    # default install in subdirectory of current workingdir:
    INSTALL_DIR = './imageserver/'
    SUPPRESS_INSTALLATION = False

PIP_PACKAGES_COMMON = [
    "fastapi==0.89.1",
    "googlemaps==4.10.0",
    "keyboard==0.13.5",
    "opencv_python==4.7.0.68",
    "piexif==1.1.3",
    "Pillow==9.4.0",
    "psutil==5.9.4",
    "pydantic==1.10.4",
    "pymitter==0.4.0",
    "PyTurboJPEG==1.7.0",
    "pywifi==1.1.12",
    "requests==2.28.2",
    "sse_starlette==1.2.1",
    "transitions==0.9.0",
    "uvicorn==0.20.0",
    "pydantic[dotenv]",
]

PIP_PACKAGES_LINUX = [
    "v4l2py==0.6.2",
]

PIP_PACKAGES_WIN = [
    "comtypes",  # for pywifi; pywifi misses to install required package comtypes
]

PIP_PACKAGES_RPI = [
    "rpi_ws281x==4.3.4",
    "gpiozero==1.6.2",
]

SYSTEM_PACKAGES_LINUX = [
    "git",
    "fonts-noto-color-emoji",
    "libturbojpeg0",
    "rclone",
    "inotify-tools"
]
SYSTEM_PACKAGES_RPI = [
    "python3-picamera2",
]


def install_system_packages_win():
    print("... not supported. Please manually install whats necessary.")
    print("Consider: digicamcontrol, python3, turbojpeg")
    print("see manual how to install packages on windows platform")
    print()


def install_system_packages_linux():
    _syscall(
        f'apt install -y {" ".join(SYSTEM_PACKAGES_LINUX)}')
    if _is_rpi():
        _syscall(
            f'apt install -y {" ".join(SYSTEM_PACKAGES_RPI)}')


def install_pip_packages():
    # install total requirements line by line to continue if some packages fail (linux/win use different packages)
    print_spacer(f"Installing pip packages")
    pip_OK = []
    pip_FAIL = []
    pip_install_packages = PIP_PACKAGES_COMMON

    if platform.system() == "Linux":
        pip_install_packages += PIP_PACKAGES_LINUX
        if _is_rpi():
            pip_install_packages += PIP_PACKAGES_RPI
    if platform.system() == "Windows":
        pip_install_packages += PIP_PACKAGES_WIN

    print(pip_install_packages)

    for package in pip_install_packages:
        retval = _syscall(
            f"python3 -m pip install --upgrade {package}")
        if retval == 0:
            pip_OK.append(package)
        else:
            pip_FAIL.append(package)
    print_spacer("pip install summary:")
    print_green("packages successfully installed:")
    print_green(pip_OK)
    print_red("packages failed to install:")
    print_red(pip_FAIL)
    print_red(
        "please check why packages failed to install. some packages might not be necessary on all platforms")


"""
HELPER
"""


def _syscall(cmd):
    print(f"execute command '{cmd}'")
    if _is_linux():
        result = subprocess.run(
            cmd,
            # capture_output=True,
            shell=True,
            text=True)
    elif _is_windows():
        result = subprocess.run(
            ["powershell", "-Command", cmd],
            # capture_output=True,
            shell=True,
            text=True)
    else:
        print("unsupported platform, exit")
        quit(-1)
    # print("commands stdout/stderr output:")
    # print(result.stdout)
    # print(result.stderr)
    print('returned value:', result.returncode)
    return result.returncode


def print_spacer(msg=None):
    print()
    if msg:
        print("╔══════════════════════════")
        print(f"║ {msg}")
        print("╚══════════════════════════")
    else:
        print("═══════════════════════════")


def _is_windows():
    return platform.system() == "Windows"


def _is_linux():
    return platform.system() == "Linux"


def _is_rpi():
    is_rpi = False
    if platform.system() == "Linux":
        if os.path.isfile("/proc/device-tree/model"):
            with open('/proc/device-tree/model', 'r') as f:
                model = f.read()
                is_rpi = "Raspberry" in model

    return is_rpi


def _is_admin():
    try:
        is_admin = os.getuid() == 0
    except AttributeError:
        is_admin = ctypes.windll.shell32.IsUserAnAdmin() != 0

    return is_admin


def query_yes_no(question, default="yes"):
    """Ask a yes/no question via raw_input() and return their answer.

    "question" is a string that is presented to the user.
    "default" is the presumed answer if the user just hits <Enter>.
            It must be "yes" (the default), "no" or None (meaning
            an answer is required of the user).

    The "answer" return value is True for "yes" or False for "no".
    """
    valid = {"yes": True, "y": True, "ye": True, "no": False, "n": False}
    if default is None:
        prompt = " [y/n] "
    elif default == "yes":
        prompt = " [Y/n] "
    elif default == "no":
        prompt = " [y/N] "
    else:
        raise ValueError("invalid default answer: '%s'" % default)

    while True:
        sys.stdout.write(question + prompt)
        choice = input().lower()
        if default is not None and choice == "":
            return valid[default]
        elif choice in valid:
            return valid[choice]
        else:
            sys.stdout.write(
                "Please respond with 'yes' or 'no' " "(or 'y' or 'n').\n")


def print_green(msg):
    print(f"{_style.GREEN}{msg}{_style.RESET}")


def print_red(msg):
    print(f"{_style.RED}{msg}{_style.RESET}")


def print_blue(msg):
    print(f"{_style.BLUE}{msg}{_style.RESET}")


class _style():
    RED = '\033[31m'
    GREEN = '\033[32m'
    BLUE = '\033[34m'
    RESET = '\033[0m'


"""
# check prerequisites
"""
print_spacer("checking for admin rights")
# need sudo/admin
if _is_linux() and not _is_admin():
    print_red("Error, please start installer with admin priviliges")
    quit(-1)
else:
    print_green("OK")

if _is_windows():
    print_spacer("checking for digicamcontrol")
    if os.path.isfile("C:\Program Files (x86)\digiCamControl\CameraControlCmd.exe"):
        print_green("OK, executable found")
    else:
        print_blue(
            "Info, digicamcontrol not found - please install if digicamintegration shall be used.")


print_spacer(f"python version > {MIN_PYTHON_VERSION}?")
print_blue(f"Python version {sys.version}")
if sys.version_info < MIN_PYTHON_VERSION:
    print_red(f"error, need at least python version {MIN_PYTHON_VERSION}")
    quit(-1)
else:
    print_green("OK")


print_spacer(f"Is Raspberry Pi?")
if _is_rpi():
    print_blue("OK, Pi detected")
else:
    print_blue("No Pi, will not install Pi specific features")


"""
installation procedure
"""
print()

# update system
if platform.system() == "Linux":
    _syscall('apt update')
    if query_yes_no("Update system packages?", "no"):
        _syscall('apt upgrade -y')

# install system dependencies
if query_yes_no("Install system packages?", "no"):
    if platform.system() == "Linux":
        print(f"Installing Linux system packages")
        install_system_packages_linux()
    elif platform.system() == "Windows":
        print(f"Installing Windows system packages")
        install_system_packages_win()
    else:
        print("unsupported platform, exit")
        quit(-1)

# install pip packages
if query_yes_no("Install pip packages?", "no"):
    install_pip_packages()

# install gphoto2
if _is_linux():
    if query_yes_no("Install gphoto2 using gphoto2-updater?", "no"):
        # adds missing packages on debian buster that are not covered by the updater script
        _syscall("apt install -y libpopt0 libpopt-dev libexif-dev")
        _syscall(
            "mkdir tmp_gphoto2_install; cd tmp_gphoto2_install; wget https://raw.githubusercontent.com/gonzalo/gphoto2-updater/master/gphoto2-updater.sh")
        _syscall(
            "cd tmp_gphoto2_install; wget https://raw.githubusercontent.com/gonzalo/gphoto2-updater/master/.env")
        _syscall("cd tmp_gphoto2_install; chmod +x gphoto2-updater.sh")
        _syscall("cd tmp_gphoto2_install; ./gphoto2-updater.sh --stable")

# install booth software
if not SUPPRESS_INSTALLATION:
    if query_yes_no("Install booth software?", "no"):
        print("Installing qBooth to ~/imageserver/")
        if query_yes_no("install dev preview? if no install stable", "no"):
            _syscall(
                f"git clone --branch dev https://github.com/mgrl/photobooth-imageserver.git {INSTALL_DIR}")
        else:
            _syscall(
                f"git clone https://github.com/mgrl/photobooth-imageserver.git {INSTALL_DIR}")

if platform.system() == "Linux":
    _syscall(
        f"chmod +x {INSTALL_DIR}start.sh")

print()
# install booth service
if query_yes_no("Install booth service?", "no"):
    if _is_linux():

        with open("imageserver.service", "rt") as fin:
            with open("/etc/systemd/system/imageserver.service", "wt") as fout:
                for line in fin:
                    fout.write(line.replace('##install_dir##',
                               os.path.normpath(f"{Path.cwd()}/{INSTALL_DIR}")))

        _syscall("systemctl enable imageserver.service")
        # _syscall("systemctl start imageserver.service")
        # _syscall("systemctl status imageserver.service")

    if _is_windows():
        print_red(
            "not yet supported. pls start imageserver manually and browse to photobooth website.")

"""
Post install checks
"""

print_spacer("check turbojpeg installed properly")
try:
    from turbojpeg import TurboJPEG
    TurboJPEG()  # instancing throws error if lib not present (usually a problem on windows only)
except Exception as e:
    print_red(e)
    print_red("Error! Install turbojpeg from https://libjpeg-turbo.org/")
    print_red(
        "On Windows use VC version and ensure its located in this path: C:/libjpeg-turbo64/bin/turbojpeg.dll")
    quit(-1)
else:
    print_green("OK, turboJpeg detected.")


# check gphoto2 installed properly
if _is_linux():
    print_spacer("check gphoto2 properly installed")
    if not _syscall("gphoto2 --version") == 0:
        print_red(
            "Error, gphoto2 command not found, error during installation or installation not selected")
    else:
        print_green("OK, Gphoto2 installed properly")

if _is_linux() or _is_windows():
    print_spacer("checking opencv2 camera indexes")
    from scripts.available_webcams_cv2 import availableCameraIndexes
    print(availableCameraIndexes())


if _is_linux():
    print_spacer("checking v4l camera indexes")
    from scripts.available_webcams_v4l import availableCameraIndexes
    print(availableCameraIndexes())

"""
FINISH
"""

print_spacer("Installer finished")
print("start imageserver (start.sh/start.bat) and")
print("browse to localhost:8000")
