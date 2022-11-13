# Photobooth Imageserver

This small python imageserver allows to use an arducam autofocus camera in the protobooth project.
The imageserver controls camera's autofocus, handles led signaling when a photo is taken and streams live video to photobooth.

The booth is made from 3d printed parts, [see the documentation over here](https://github.com/mgrl/photobooth-3d).

## :heart_eyes: Features

- camera live preview
- permanent video live view in background
- contant autofocus based on the live preview
- utilizes arducam 16mp imx519 camera module
- led ring signaling photo countdown and when the photo is actually taken

## :gear: Prerequisites

- Python 3.9
- Arducam 16MP imx519 with autofocus motor
- Arducam drivers/libcamera apps properly installed
- [photobooth installed](https://photoboothproject.github.io/)
- [works probably best with 3d printed photobooth and parts listed in the BOM](https://github.com/mgrl/photobooth-3d)

## :wrench: Installation

Install packages (as root because imageserver needs to run as root)

```text
sudo pip install event-notifier opencv-python rpi_ws281x googlemaps pywifi
sudo apt install -y python3-picamera2 git
git clone https://github.com/mgrl/photobooth-imageserver.git ~/imageserver
```

Test run the server by issuing

```text
sudo python ~/imageserver/imageserver.py
```

Browse to <http://photobooth:8000> (replace photobooth by actual hostname) and see that it is working

Now install the service:

```text
sudo cp ~/imageserver/imageserver.service /etc/systemd/system/
sudo systemctl enable imageserver.service
sudo systemctl start imageserver.service
sudo systemctl status imageserver.service
```

### Integrate with ImageServer

```text
take_picture_cmd: curl -X POST localhost:8000/capture -d 'filename=%s'
take_picture_msg: Done
pre_photo_cmd: curl localhost:8000/cmd/capturePrepare
post_photo_cmd: curl localhost:8000/cmd/autofocus/on
preview_url: url(<http://photobooth:8000/stream.mjpg>)
background_defaults: url(<http://photobooth:8000/stream.mjpg>)
```

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

- 2022-10-03
  - introduced led ring
- 2022-11-06
  - refactoring
  - rclone to sync photos online for easier download
  - store exif data to images
  - changed to exposure mode short as per default

### :copyright: License

The software is licensed under the MIT license.  

### :tada: Donation

If you like my work and like to keep me motivated you can buy me a coconut water:

[![Donate](https://img.shields.io/badge/Donate-PayPal-green.svg)](localhost)
