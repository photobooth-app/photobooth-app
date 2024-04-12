<h1 align="center"><img src="https://raw.githubusercontent.com/photobooth-app/photobooth-app/main/assets/logo/logo-text-blue-transparent.png" alt="photobooth app logo" /></h1>

Welcome to your brand-new open-source photobooth-app! Written in Python 🐍, coming along with a modern Vue3 frontend.

[![PyPI](https://img.shields.io/pypi/v/photobooth-app)](https://pypi.org/project/photobooth-app/)
![python versions supported 3.9, 3.10, 3.11](https://img.shields.io/pypi/pyversions/photobooth-app)
![rpi, linux and windows platform supported](https://img.shields.io/badge/platform-rpi%20%7C%20linux%20%7C%20windows-lightgrey)
[![ruff](https://github.com/photobooth-app/photobooth-app/actions/workflows/ruff.yml/badge.svg)](https://github.com/photobooth-app/photobooth-app/actions/workflows/ruff.yml)
[![pytest](https://github.com/photobooth-app/photobooth-app/actions/workflows/pytests.yml/badge.svg)](https://github.com/photobooth-app/photobooth-app/actions/workflows/pytests.yml)
[![codecov](https://codecov.io/gh/photobooth-app/photobooth-app/branch/main/graph/badge.svg?token=SBB5DGX17V)](https://codecov.io/gh/photobooth-app/photobooth-app)
[![Crowdin](https://badges.crowdin.net/photobooth-app/localized.svg)](https://crowdin.com/project/photobooth-app)

**[Installation](https://photobooth-app.org/setup/installation/)** - **[Documentation](https://photobooth-app.org/)** - **[PyPI package](https://pypi.org/project/photobooth-app/)** - **[3d printed box](https://photobooth-app.org/photobox3dprint/)**

## 😍 Features

📷 capture stills, animated gif, collages and even 📹 videos!  
🎉 camera live preview with shortest delay as possible, permanent video live view in background  
🛫 optimized for speed, highly response UI  
🫶 several camera backends supported for high quality stills and livestream  
💡 WLED support signaling photo countdown and feedback to the user when the photo is actually taken  
🤝 Linux 🐧, Raspberry Pi 🍓 and Windows 🪟 platforms supported  
🔓 Open-source, non-restrictive MIT license  

## 📷 Supported Cameras

The photobooth app's Python backend allows to use different camera types on Linux and Windows platforms:

- Raspberry Pi Camera Module 1/2/3 (with or without autofocus)
- Arducam cameras (with or without autofocus, not preferred because separate installation)
- DSLR camera via
  - gphoto2, Linux
  - digicamcontrol, Windows
- Webcameras (via opencv2 or v4l)

The app controls camera's autofocus, handles led signaling when a photo is taken and streams live video to photobooth.

The reference photobooth box is made from 3d printed parts, [see the 3d printed reference box over here](https://photobooth-app.org/photobox3dprint/).

## 💅 Screenshots

[Find screenshots in the documentation](https://photobooth-app.org/screenshots)

## 🔧 Installation

[See separate installation instructions in the documentation](https://photobooth-app.org/setup/installation/).

### ©️ License

The software is licensed under the MIT license.

### 🎉 Donation

If you like my work and like to keep me motivated you can sponsor me:

[![Donate](https://img.shields.io/badge/Donate-PayPal-green.svg)](https://www.paypal.com/donate/?hosted_button_id=8255Y566TBNEC)

Or help [translate the software in your language](https://github.com/photobooth-app/photobooth-app/blob/main/CONTRIBUTING.md#help-translate-the-app).
