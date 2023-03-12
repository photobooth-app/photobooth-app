# Photobooth App

_Latest stable version:_  
[![pylint](https://github.com/mgrl/photobooth-app/actions/workflows/pylint.yml/badge.svg)](https://github.com/mgrl/photobooth-app/actions/workflows/pylint.yml)
[![pytest](https://github.com/mgrl/photobooth-app/actions/workflows/python-test.yml/badge.svg)](https://github.com/mgrl/photobooth-app/actions/workflows/python-test.yml)

_Latest development version:_  
[![pylint](https://github.com/mgrl/photobooth-app/actions/workflows/pylint.yml/badge.svg?branch=dev)](https://github.com/mgrl/photobooth-app/actions/workflows/pylint.yml)
[![pytest](https://github.com/mgrl/photobooth-app/actions/workflows/python-test.yml/badge.svg?branch=dev)](https://github.com/mgrl/photobooth-app/actions/workflows/python-test.yml)

This app allows to use

- picamera2 (with or without autofocus)
- arducam cameras (with or without autofocus)
- DSLR cameras (via gphoto2 or digicamcontrol) (not yet implemented) and
- webcams (via opencv2 or v4l)

for high quality still photos and for livestream in your own photobooth.

The app controls camera's autofocus, handles led signaling when a photo is taken and streams live video to photobooth.

The booth is made from 3d printed parts, [see the documentation over here](https://github.com/mgrl/photobooth-3d).
The camera support is mostly ready to use, the frontend is not production ready yet.
Use [photobooth project](https://photoboothproject.github.io/) as frontend.

## :heart_eyes: Features

- camera live preview with shortest delay as possible
- permanent video live view in background
- autofocus based on the live preview
- several camera backends supported for still/livestream
- led ring signaling photo countdown and when the photo is actually taken

## :gear: Prerequisites

- Python 3.9 or later
- Camera supported by one of the backends
- Raspberry Pi Bullseye with libcamera stack for picamera modules
- git installed (automatic install on linux, download manually for windows platform)
- [photobooth installed](https://photoboothproject.github.io/)
- [works probably best with 3d printed photobooth and parts listed in the BOM](https://github.com/mgrl/photobooth-3d)

## :wrench: Installation

An installer is available, helping to setup on a linux or windows system.
Download the installer and start it as follows:

Linux:

```text
wget https://raw.githubusercontent.com/mgrl/photobooth-app/main/install.py
python install.py
```

Windows:

```text
curl -O https://raw.githubusercontent.com/mgrl/photobooth-app/main/install.py
python install.py
```

Browse to <http://localhost:8000> and see that it is working

### Integrate Photobooth and ImageServer

Replace <http://photobooth> by the actual hostname or localhost if on same server.

```text
take_picture_cmd: curl -X POST http://photobooth:8000/cmd/capture -H 'accept: application/json' -H 'Content-Type: application/json' -d '"%s"'
take_picture_msg: Done
pre_photo_cmd: curl http://photobooth:8000/cmd/frameserver/capturemode
post_photo_cmd: curl http://photobooth:8000/cmd/frameserver/previewmode
preview_url: url("http://photobooth:8000/stream.mjpg")
background_defaults: url("http://photobooth:8000/stream.mjpg")
```

### Countdown LED by WLED integration

Add animated lights to your photobooth powered by WLED. WLED is a fast and feature-rich implementation of an ESP8266/ESP32 webserver to control NeoPixel (WS2812B, WS2811, SK6812) LEDs.

Head over to <https://kno.wled.ge/basics/getting-started/> for installation instructions and hardware setup. Connect the ESP board via USB to the photobooth computer.

In the WLED webfrontend define three presets:

- ID 1: standby (usually LEDs off)
- ID 2: countdown (animates countdown)
- ID 3: shoot (imitate a flash)

Please define presets on your own in WLED webfrontend. Once added, in the photobooth enable the WLED integration and provide the serial port. Check logs on startup whether the module is detected correctly.

### Sync Online (for file downloads via QR Code)

```text
sudo apt-get install rclone inotify-tools
```

```text
rclone config
```

Setup the remote named "boothupload"!

```text
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

```text
# logfiles from service (last 200 lines)
journalctl --user --unit=imageserver -n 200 --no-pager
# logfiles created by photobooth
cat ~/imageserver/log/qbooth.log
# check CmaFree especially for Arducams if low:
cat /proc/meminfo
```

If service crashed, kill the python process:

```text
sudo pkill -9 python3
```

### :copyright: License

The software is licensed under the MIT license.  

### :tada: Donation

If you like my work and like to keep me motivated you can buy me a coconut water:

[![Donate](https://img.shields.io/badge/Donate-PayPal-green.svg)](https://www.paypal.com/donate/?hosted_button_id=8255Y566TBNEC)
