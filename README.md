# Photobooth App

The photobooth app is written in Python and coming along with a modern Vue frontend.

[![pylint](https://github.com/mgrl/photobooth-app/actions/workflows/pylint.yml/badge.svg)](https://github.com/mgrl/photobooth-app/actions/workflows/pylint.yml)
[![pytest](https://github.com/mgrl/photobooth-app/actions/workflows/pytest.yml/badge.svg)](https://github.com/mgrl/photobooth-app/actions/workflows/pytest.yml)

## :heart_eyes: Features

- camera live preview with shortest delay as possible
- permanent video live view in background
- autofocus based on the live preview
- several camera backends supported for high quality stills and livestream
- WLED support signaling photo countdown and feedback to the user when the photo is actually taken

## :camera: Supported Cameras

The photobooth app's Python backend allows to use different camera types on Linux and Windows platforms:

- Raspberry Pi Camera Module 1/2/3 (with or without autofocus)
- Arducam cameras (with or without autofocus)
- DSLR camera via
  - gphoto2, Linux
  - digicamcontrol, Windows (not yet implemented)
- webcams (via opencv2 or v4l)

The app controls camera's autofocus, handles led signaling when a photo is taken and streams live video to photobooth.

The booth is made from 3d printed parts, [see the documentation over here](https://github.com/mgrl/photobooth-3d).
The camera support is mostly ready to use, the frontend is not production ready yet.
Use [photobooth project](https://photoboothproject.github.io/) as frontend.

## :gear: Prerequisites

- Python 3.9 or later
- Camera supported by one of the backends
- Raspberry Pi Bullseye with libcamera stack for picamera modules
- git installed (automatic install on linux, download manually for windows platform)
- [works probably best with 3d printed photobooth and parts listed in the BOM](https://github.com/mgrl/photobooth-3d)

The photobooth app can be used standalone but is not feature complete yet.
Anyway, it integrates well with the fully blown [photobooth project](https://photoboothproject.github.io/),
see description below how to achieve integration.

## :wrench: Installation

Execute the installer following the commands below, helping to setup on a Linux or Windows system:

```sh
curl -o install.py https://raw.githubusercontent.com/mgrl/photobooth-app/main/install.py
python install.py
```

Start the app and browse to <http://localhost:8000>, start using the app.

```sh
cd imageserver
python start.py
```

### Integrate Photobooth-Project and this Photobooth-App

Following commands have to be set in photobooth project to use this app as imageserver.
Replace <http://photobooth> by the actual hostname or localhost if on same server.

```text
take_picture_cmd: curl -X POST http://photobooth:8000/cmd/capture -d '"%s"'
take_picture_msg: Done
pre_photo_cmd: curl http://photobooth:8000/cmd/imageserver/capturemode
post_photo_cmd: curl http://photobooth:8000/cmd/imageserver/previewmode
preview_url: url("http://photobooth:8000/stream.mjpg")
background_defaults: url("http://photobooth:8000/stream.mjpg")
```

### WLED integration for LED signaling

Add animated lights to your photobooth powered by WLED. WLED is a fast and feature-rich implementation of an ESP8266/ESP32 webserver to control NeoPixel (WS2812B, WS2811, SK6812) LEDs.

Head over to <https://kno.wled.ge/basics/getting-started/> for installation instructions and hardware setup. Connect the ESP board via USB to the photobooth computer.

In the WLED webfrontend define three presets:

- ID 1: standby (usually LEDs off)
- ID 2: countdown (animates countdown)
- ID 3: shoot (imitate a flash)

Please define presets on your own in WLED webfrontend. Once added, in the photobooth enable the WLED integration and provide the serial port. Check logs on startup whether the module is detected correctly.

### Sync Online (for file downloads via QR Code)

```sh
sudo apt-get install rclone inotify-tools
```

```sh
rclone config
```

Setup the remote named "boothupload"!

```sh
chmod u+x ~/imageserver/boothupload.sh
cp ~/imageserver/boothupload.service ~/.config/systemd/user/
systemctl --user enable boothupload.service
systemctl --user start boothupload
systemctl --user status boothupload
```

### Setup Wifi and Hotspot

At home prefer local wifi with endless data. If this is not available connect to a mobile hotspot for online sync.

In file /etc/wpa_supplicant/wpa_supplicant.conf set a priority for local and hotspot wifi:

```text
network={
    ssid="homewifi"
    psk="passwordOfhomewifi"
    priority=10
}
network={
   ssid="mobileexpensivewifi"
   psk="passwordOfmobileexpensivewifi"
   priority=5
}
```

## :mag: Changelog

- 2023-04-13
  - revised statemachine
  - changed api commands for photobooth
  - removed locationservice and extended exif for now
  - FIX: switch_mode hangs forever, replaced by configure. needs more testing
- 2023-04-08
  - picamera2 now with gpu hardware acceleration reduce cpu load
  - gphoto2 implemented
  - frontend polished
  - removed custom autofocus method (not compatible with gpu acceleration)
  - many smaller improvements
  - many bugfixes
- 2023-02-26
  - added pytest and set up automated tests
  - fixed some performance issues using separate processes to exploit cpu better
  - fixed performance issue when connecting multiple clients on eventstream
  - improved installer
  - pydantic config management fully presented in user interface via blitzar
  - many smaller improvements
  - many bugfixes
- 2023-02-05
  - added several camera backends (working: v4l, opencv, simulated, picamera2; not yet working: gphoto2, digicamcontrol)
  - added installer
  - removed rpiws2811 and integrated WLED to be platform independent
  - keyboard reads without root permission - whole app now runs as normal user
  - pydantic config management via json and env files
- 2022-10-03
  - introduced led ring
- 2022-11-06
  - refactoring
  - rclone to sync photos online for easier download
  - store exif data to images
  - changed to exposure mode short as per default

## Contribute

If you find an issue, please post it <https://github.com/mgrl/photobooth-app/issues>

Develop on Windows or Linux using VScode.
Additional requirements

- backend development
  - pip install pipreqs
  - pip install pytest
- frontend development
  - nodejs 16 (nodejs 18 fails proxying the devServer)
  - yarn
  - quasar cli <https://quasar.dev/start/quasar-cli>

## Troubleshooting

Check following commands and files for error messages:

```zsh
# logfiles from service (last 200 lines)
journalctl --user --unit=imageserver -n 200 --no-pager
# logfiles created by photobooth
cat ~/imageserver/log/qbooth.log
# check CmaFree especially for Arducams if low:
cat /proc/meminfo
```

If service crashed, kill the python process:

```zsh
sudo pkill -9 python3
```

### Check available webcam device numbers

```zsh
python -c "from src.imageserverwebcamv4l import *; print(available_camera_indexes())"
python -c "from src.imageserverwebcamcv2 import *; print(available_camera_indexes())"

```

### :copyright: License

The software is licensed under the MIT license.  

### :tada: Donation

If you like my work and like to keep me motivated you can buy me a coconut water:

[![Donate](https://img.shields.io/badge/Donate-PayPal-green.svg)](https://www.paypal.com/donate/?hosted_button_id=8255Y566TBNEC)
