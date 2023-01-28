import os
import ctypes
import sys
import subprocess
import platform
from pathlib import Path

MIN_PYTHON_VERSION = (3, 9)
INSTALL_DIR = './imageserver/'

print(INSTALL_DIR)


def install_system_packages_win():
    print("nothing to install actually")


def install_system_packages_linux():
    _syscall(
        'apt install -y python3-picamera2 git fonts-noto-color-emoji libturbojpeg0')
    _syscall('apt install -y rclone inotify-tools')


def install_pip_packages():
    # install total requirements line by line to continue if some packages fail (linux/win use different packages)
    print(f"Installing pip packages")
    pip_OK = []
    pip_FAIL = []
    with open("requirements.txt") as fp:
        for line in fp:
            package = line.strip()
            retval = _syscall(
                f"python3 -m pip install --upgrade {package}")
            if retval == 0:
                pip_OK.append(package)
            else:
                pip_FAIL.append(package)
    print("pip install summary:")
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
    if platform.system() == "Linux":
        result = subprocess.run(
            cmd,
            capture_output=True,
            shell=True,
            text=True)
    elif platform.system() == "Windows":
        result = subprocess.run(
            ["powershell", "-Command", cmd],
            capture_output=True,
            shell=True,
            text=True)
    else:
        print("unsupported platform, exit")
        quit(-1)
    print("commands stdout/stderr output:")
    print(result.stdout)
    print(result.stderr)
    print('returned value:', result.returncode)
    return result.returncode


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

# need sudo/admin
if platform.system() == "Linux" and not _is_admin():
    print_red("please start installer with admin priviliges")
    quit(-1)

# - digicamcontrol

print_blue(f"Python version {sys.version}")
if sys.version_info < MIN_PYTHON_VERSION:
    print_red(f"error, need at least python version {MIN_PYTHON_VERSION}")
    quit(-1)


"""
installation procedure
"""


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
if platform.system() == "Linux":
    if query_yes_no("Install gphoto2 using gphoto2-updater?", "no"):
        # adds missing packages on debian buster that are not covered by the updater script
        _syscall("apt install -y libpopt0 libpopt-dev libexif-dev")
        _syscall(
            "wget https://raw.githubusercontent.com/gonzalo/gphoto2-updater/master/gphoto2-updater.sh")
        _syscall(
            "wget https://raw.githubusercontent.com/gonzalo/gphoto2-updater/master/.env")
        _syscall("chmod +x gphoto2-updater.sh")
        _syscall("./gphoto2-updater.sh --stable")

# install booth software
if query_yes_no("Install booth software?", "yes"):
    print("Installing qBooth to ~/imageserver/")
    if query_yes_no("install dev preview? if no install stable", "no"):
        _syscall(
            f"git clone --branch dev https://github.com/mgrl/photobooth-imageserver.git {INSTALL_DIR}")
    else:
        _syscall(
            f"git clone https://github.com/mgrl/photobooth-imageserver.git {INSTALL_DIR}")

    _syscall(
        f"chmod +x {INSTALL_DIR}start.sh")

# install booth service
if query_yes_no("Install booth service?", "yes"):
    pass


"""
Post install checks
"""

# check turbojpeg installed properly
try:
    from turbojpeg import TurboJPEG
    TurboJPEG()  # instancing throws error if lib not present (usually a problem on windows only)
except Exception as e:
    print_red(e)
    print_red("Error! Install turbojpeg from https://libjpeg-turbo.org/")
    print_red(
        "On Windows ensure its located in this path: C:/libjpeg-turbo64/bin/turbojpeg.dll")
    quit(-1)
else:
    print_green("TurboJpeg detected.")


# check gphoto2 installed properly
if platform.system() == "Linux":
    if not _syscall("gphoto2 --version") == 0:
        print_red(
            "gphoto2 command not found, error during installation or installation not selected")
    else:
        print_green("Gphoto2 installed properly")


"""
FINISH
"""

print("Install script finished")
