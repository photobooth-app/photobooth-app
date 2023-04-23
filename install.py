"""
Installer
"""
from subprocess import call, STDOUT
import socket
import getpass
import os.path
import os
import ctypes
import sys
import subprocess
import platform
from dataclasses import dataclass
from importlib.metadata import version
from pathlib import Path
from src.utils import is_rpi

MIN_PYTHON_VERSION = (3, 9)
USERNAME = getpass.getuser()

if os.path.isfile("start.py"):
    # if imageserver.py is detected, assume the sourcecode was already copied to target computer
    # useful if just want to enable service, install desktop shortcut, ...
    INSTALL_DIR = "./"
    SUPPRESS_INSTALLATION = True
else:
    # default install in subdirectory of current workingdir:
    INSTALL_DIR = "./imageserver/"
    SUPPRESS_INSTALLATION = False
    sys.path.append(INSTALL_DIR)
    # ensure dir exists
    Path(INSTALL_DIR).mkdir(exist_ok=True)

SYSTEM_PACKAGES_LINUX = [
    "git",
    "libgl1",  # install opencv dependencies from distro, needed on fresh rpi os
    "fonts-noto-color-emoji",
    "libturbojpeg0",
    "rclone",
    "inotify-tools",
    "python3-pip",
]
SYSTEM_PACKAGES_RPI = [
    "python3-picamera2",
]


STARTER_CONFIGURATIONS_COMMON = [
    (
        "windows-and-linux_webcam_opencv2",
        """
backends__MAIN_BACKEND="ImageServerWebcamCv2"
backends__cv2_device_index=##cv2_device_index##
common__CAPTURE_CAM_RESOLUTION_WIDTH=10000
common__CAPTURE_CAM_RESOLUTION_HEIGHT=10000
""",
    ),
]

STARTER_CONFIGURATIONS_LINUX = [
    (
        "linux_webcam_v4l",
        """
backends__MAIN_BACKEND="ImageServerWebcamV4l"
backends__v4l_device_index=##v4l_device_index##
""",
    ),
]

STARTER_CONFIGURATIONS_WIN = [
    # none yet
]

STARTER_CONFIGURATIONS_RPI = [
    (
        "rpi_picam2_cameramodule3_native_libcamera",
        """
backends__MAIN_BACKEND="ImageServerPicam2"
backends__picam2_focuser_module="LibcamAfContinuous"
common__CAPTURE_CAM_RESOLUTION_WIDTH="4608"
common__CAPTURE_CAM_RESOLUTION_HEIGHT="2592"
common__PREVIEW_CAM_RESOLUTION_WIDTH="2304"
common__PREVIEW_CAM_RESOLUTION_HEIGHT="1296"
""",
    ),
    (
        "rpi_picam2_arducam_imx519_native_libcamera",
        """
backends__MAIN_BACKEND="ImageServerPicam2"
backends__picam2_focuser_module="LibcamAfInterval"
common__CAPTURE_CAM_RESOLUTION_WIDTH="4656"
common__CAPTURE_CAM_RESOLUTION_HEIGHT="3496"
common__PREVIEW_CAM_RESOLUTION_WIDTH="2328"
common__PREVIEW_CAM_RESOLUTION_HEIGHT="1748"
""",
    ),
    (
        "rpi_picam2_arducam_64mp_arducams_libcamera",
        """
backends__MAIN_BACKEND="ImageServerPicam2"
backends__picam2_focuser_module="LibcamAfInterval"
common__CAPTURE_CAM_RESOLUTION_WIDTH="4624"
common__CAPTURE_CAM_RESOLUTION_HEIGHT="3472"
common__PREVIEW_CAM_RESOLUTION_WIDTH="2312"
common__PREVIEW_CAM_RESOLUTION_HEIGHT="1736"
""",
    ),
]


def install_system_packages_win():
    """_summary_"""
    print("... not supported. Please manually install whats necessary.")
    print("Consider: digicamcontrol, python3, turbojpeg")
    print("see manual how to install packages on windows platform")
    print()


def install_system_packages_linux():
    """_summary_"""
    _syscall(f'apt install -y {" ".join(SYSTEM_PACKAGES_LINUX)}', True)
    if is_rpi():
        _syscall(f'apt install -y {" ".join(SYSTEM_PACKAGES_RPI)}', True)


def install_pip_packages():
    """_summary_"""
    # install total requirements line by line to continue if some packages fail
    # (linux/win use different packages)
    print_spacer("Installing pip packages")

    retval = _syscall("pip install -r requirements.txt", cwd=INSTALL_DIR)
    if retval != 0:
        print_red("pip installation failed! check output for errors")
        sys.exit()

    print_green("All packages successfully installed")


#
# HELPER
#


def _syscall(cmd: str, sudo: bool = False, cwd="./"):
    print_spacer(f"run '{cmd=}', {sudo=}, {cwd=}")
    if _is_linux():
        if sudo is True:
            cmd = f"sudo {cmd}"
        result = subprocess.run(cmd, shell=True, text=True, check=False, cwd=cwd)
    elif _is_windows():
        result = subprocess.run(
            ["powershell", "-Command", cmd], shell=True, text=True, check=False, cwd=cwd
        )
    else:
        print("unsupported platform, exit")
        sys.exit(-1)

    print("command exited with returncode=", result.returncode)
    return result.returncode


def print_spacer(msg=None):
    """_summary_

    Args:
        msg (_type_, optional): _description_. Defaults to None.
    """
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
        raise ValueError(f"invalid default answer: {default}")

    while True:
        sys.stdout.write(question + prompt)
        choice = input().lower()
        if default is not None and choice == "":
            return valid[default]
        if choice in valid:
            return valid[choice]

        sys.stdout.write("Please respond with 'yes' or 'no' (or 'y' or 'n').\n")


def print_green(msg):
    """_summary_

    Args:
        msg (_type_): _description_
    """
    print(f"{_style.GREEN}{msg}{_style.RESET}")


def print_red(msg):
    """_summary_

    Args:
        msg (_type_): _description_
    """
    print(f"{_style.RED}{msg}{_style.RESET}")


def print_blue(msg):
    """_summary_

    Args:
        msg (_type_): _description_
    """
    print(f"{_style.BLUE}{msg}{_style.RESET}")


@dataclass
class _style:
    RED = "\033[31m"
    GREEN = "\033[32m"
    BLUE = "\033[34m"
    RESET = "\033[0m"


#
# check prerequisites
#
print_spacer("current user")
print_blue(f"{USERNAME}")
if _is_linux() and _is_admin():
    print_red(
        "Error, please start installer as normal user, "
        "for specific tasks the script will ask for permission"
    )
    sys.exit(-1)
else:
    print_green("OK")

if _is_windows():
    print_spacer("checking for digicamcontrol")
    if os.path.isfile(r"C:\Program Files (x86)\digiCamControl\CameraControlCmd.exe"):
        print_green("OK, executable found")
    else:
        print_blue(
            "Info, digicamcontrol not found - please install if digicamintegration shall be used."
        )


print_spacer(f"python version > {MIN_PYTHON_VERSION}?")
print_blue(f"Python version {sys.version}")
if sys.version_info < MIN_PYTHON_VERSION:
    print_red(f"error, need at least python version {MIN_PYTHON_VERSION}")
    sys.exit(-1)
else:
    print_green("OK")


print_spacer("Is Raspberry Pi?")
if is_rpi():
    print_blue("OK, Pi detected")
else:
    print_blue("No Pi, will not install Pi specific features")


#
# installation procedure
#
print()

# update system
if platform.system() == "Linux":
    if query_yes_no("Update and upgrade system packages?", "no"):
        _syscall("apt update", True)
        _syscall("apt upgrade -y", True)

# install system dependencies
if query_yes_no("Install system packages required for booth?", "yes"):
    if platform.system() == "Linux":
        print("Installing Linux system packages")
        _syscall("apt update", True)
        install_system_packages_linux()
    elif platform.system() == "Windows":
        print("Installing Windows system packages")
        install_system_packages_win()
    else:
        print("unsupported platform, exit")
        sys.exit(-1)


# check git prerequisite
print_spacer("check git properly installed")
if not _syscall("git --version") == 0:
    print_red("Error, git not found. Install git from https://git-scm.com/")
    sys.exit(-1)
else:
    print_green("OK, git installed properly")
    print()

# fix keyboard input permissions
if _is_linux():
    print_spacer(f"add '{USERNAME}' to tty and input groups for keyboard access")
    _syscall(f"usermod --append --groups tty,input {USERNAME}", True)


# install gphoto2
if _is_linux():
    if query_yes_no("Install gphoto2 using gphoto2-updater?", "no"):
        # adds missing packages on debian buster that are not covered by the updater script
        _syscall("apt install -y libpopt0 libpopt-dev libexif-dev", True)
        _syscall("mkdir tmp_gphoto2_install; ")
        _syscall(
            "wget https://raw.githubusercontent.com/gonzalo/gphoto2-updater/master/gphoto2-updater.sh",  # pylint: disable=line-too-long
            cwd="tmp_gphoto2_install",
        )
        _syscall(
            "wget https://raw.githubusercontent.com/gonzalo/gphoto2-updater/master/.env",
            cwd="tmp_gphoto2_install",
        )
        _syscall(
            "chmod +x gphoto2-updater.sh",
            cwd="tmp_gphoto2_install",
        )
        _syscall(
            "./gphoto2-updater.sh --stable",
            True,
            cwd="tmp_gphoto2_install",
        )
        _syscall("rm -r tmp_gphoto2_install", True)

# install booth software
INSTALLDIR_HAS_GIT_REPO = (
    call(
        ["git", "branch"],
        cwd=INSTALL_DIR,
        stderr=STDOUT,
        stdout=open(os.devnull, "w", encoding="utf-8"),  # pylint: disable=R1732
    )
    == 0
)
if not SUPPRESS_INSTALLATION and not INSTALLDIR_HAS_GIT_REPO:
    if query_yes_no(f"Install booth software to {INSTALL_DIR}?", "no"):
        try:
            os.mkdir(INSTALL_DIR)
        except FileExistsError:
            pass  # silent ignore if already exists

        # subdir has no git repo yet - considered as new installation
        print("Installing qBooth to ./imageserver/")
        if query_yes_no("install dev preview? if no install stable", "no"):
            _syscall(
                f"git clone --branch dev https://github.com/mgrl/photobooth-app.git {INSTALL_DIR}"
            )
        else:
            _syscall(
                f"git clone https://github.com/mgrl/photobooth-app.git {INSTALL_DIR}"
            )


if INSTALLDIR_HAS_GIT_REPO:
    if query_yes_no(f"Update booth software in {INSTALL_DIR}, by git pull?", "no"):
        print(f"Updating qBooth in subdir {INSTALL_DIR}")
        _syscall("git pull", cwd=INSTALL_DIR)

if platform.system() == "Linux":
    _syscall(f"chmod +x {INSTALL_DIR}start.sh")


# install pip packages
if query_yes_no("Install/Upgrade pip packages for booth?", "yes"):
    install_pip_packages()


# install booth service
if query_yes_no("Install booth service?", "no"):
    if _is_linux():
        with open(
            f"{INSTALL_DIR}/misc/installer/imageserver.service", "rt", encoding="utf-8"
        ) as fin:
            compiled_service_file = Path(
                f"{str(Path.home())}/.local/share/systemd/user/imageserver.service"
            )
            compiled_service_file.parent.mkdir(exist_ok=True, parents=True)
            print_blue(f"creating service file '{compiled_service_file}'")
            with open(str(compiled_service_file), "wt", encoding="utf-8") as fout:
                for line in fin:
                    fout.write(
                        line.replace(
                            "##install_dir##",
                            os.path.normpath(f"{Path.cwd()}/{INSTALL_DIR}"),
                        )
                    )

        _syscall("systemctl --user enable imageserver.service")

    if _is_windows():
        print_red(
            "not yet supported. pls start imageserver manually and browse to photobooth website."
        )


# compatibility for photobooth? photobooth runs as www-data;
# the imageserver needs to write the image to given location - only possible with www-data rights:
if _is_linux():
    if query_yes_no(
        "Fix permissions to be compatible to https://photoboothproject.github.io/",
        "no",
    ):
        _syscall(f"usermod --append --groups www-data {USERNAME}", True)
        _syscall("chmod -R 775 /var/www/html", True)


#
# Post install checks
#

print_spacer("check turbojpeg installed properly")
try:
    import importlib

    # import via importlib in case turbojpeg is installed first time via pip
    # standard import turbojpeg would fail in this case
    turbojpeg = importlib.import_module("turbojpeg")

    turbojpeg.TurboJPEG()  # instancing throws error if lib not present
except RuntimeError as exc:
    print_red(exc)
    print_red("Error! Install turbojpeg from https://libjpeg-turbo.org/")
    print_red(
        "On Windows use VC version and ensure its located in this path: "
        "C:/libjpeg-turbo64/bin/turbojpeg.dll"
    )
    sys.exit(-1)
else:
    print_green("OK, turboJpeg detected.")


try:
    print_spacer("check installed picamera2 version")
    print_blue(version("picamera2"))

    print_blue(
        "Check the version is up to date. Usually updates received automatically."
    )
    print_blue(
        "If version is outdated, ensure picamera2 is NOT installed via pip. To uninstall:"
    )
    print_blue("pip uninstall picamera2 (might need sudo)")
except importlib.metadata.PackageNotFoundError:
    print("picamera2 not installed")

# check gphoto2 installed properly
if _is_linux():
    print_spacer("check gphoto2 properly installed")
    if not _syscall("gphoto2 --version") == 0:
        print_red(
            "Error, gphoto2 command not found, "
            "error during installation or installation not selected"
        )
    else:
        print_green("OK, Gphoto2 installed properly")

print_spacer("list available serial ports (use for WLED integration)")
_syscall("python -m serial.tools.list_ports")

ind_cv2 = []
ind_v4l = []
if _is_linux() or _is_windows():
    print_spacer("checking for available opencv2 cameras")
    # suppress warnings during index probing
    os.environ["OPENCV_LOG_LEVEL"] = "SILENT"
    from src.imageserverwebcamcv2 import available_camera_indexes

    ind_cv2 = available_camera_indexes()
    if ind_cv2:
        print_green("found cameras, use one of the following device numbers:")
        print(ind_cv2)
    else:
        print_red("no webcamera found")


if _is_linux():
    print_spacer("checking for available v4l cameras")
    from src.imageserverwebcamv4l import available_camera_indexes

    ind_v4l = available_camera_indexes()
    if ind_v4l:
        print_green("found cameras, use one of the following device numbers:")
        print(ind_v4l)
    else:
        print_red("no webcamera found")

print_spacer("Apply starter configuration for popular hardware choices?")
print("Choose from following list:")
availableConfigurations = STARTER_CONFIGURATIONS_COMMON
if is_rpi():
    availableConfigurations.extend(STARTER_CONFIGURATIONS_RPI)
if _is_linux():
    availableConfigurations.extend(STARTER_CONFIGURATIONS_LINUX)
if _is_windows():
    availableConfigurations.extend(STARTER_CONFIGURATIONS_WIN)
choices = list(zip(*availableConfigurations))[0]
for idx, x in enumerate(choices):
    print(idx, x)
chosen_starter_configuration_str = input(
    "Choose number of starter configuration [leave empty to skip]: "
)
if chosen_starter_configuration_str:
    chosen_starter_configuration_idx = int(chosen_starter_configuration_str)
    chosen_starter_configuration_name = availableConfigurations[
        chosen_starter_configuration_idx
    ][0]
    chosen_starter_configuration_settings = availableConfigurations[
        chosen_starter_configuration_idx
    ][1]

    CV2_DEVICE_INDEX = ind_cv2[0] if ind_cv2 else 0
    V4L_DEVICE_INDEX = ind_v4l[0] if ind_v4l else 0
    chosen_starter_configuration_settings = (
        chosen_starter_configuration_settings.replace(
            "##cv2_device_index##", str(CV2_DEVICE_INDEX)
        )
    )
    chosen_starter_configuration_settings = (
        chosen_starter_configuration_settings.replace(
            "##v4l_device_index##", str(V4L_DEVICE_INDEX)
        )
    )

    print_blue(
        f"chosen starter configuration number {chosen_starter_configuration_idx}: "
        f"{chosen_starter_configuration_name}"
    )
    print(f"{chosen_starter_configuration_settings}")
    with open(str(f"{INSTALL_DIR}.env.installer"), "wt", encoding="utf-8") as fout:
        fout.writelines(chosen_starter_configuration_settings)
    print_blue("start configuration written to .env.installer")

else:
    print_blue("skipping starter configuration")


#
# FINISH
#
print_spacer("Installer finished")
print()
print()
print("Start imageserver (start.sh/start.bat) and")
print(f"browse to http://{socket.gethostname()}:8000")
print()
print()
