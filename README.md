![photobooth-app logo](https://raw.githubusercontent.com/mgrl/photobooth-app/dev/assets/logo/logo-text-black-transparent.png)

![python versions supported 3.9, 3.10, 3.11](https://img.shields.io/pypi/pyversions/photobooth-app)
![rpi, linux and windows platform supported](https://img.shields.io/badge/platform-rpi%20%7C%20linux%20%7C%20windows-lightgrey)
[![ruff](https://github.com/mgrl/photobooth-app/actions/workflows/ruff.yml/badge.svg)](https://github.com/mgrl/photobooth-app/actions/workflows/ruff.yml)
[![pytest](https://github.com/mgrl/photobooth-app/actions/workflows/pytests.yml/badge.svg)](https://github.com/mgrl/photobooth-app/actions/workflows/pytests.yml)
[![codecov](https://codecov.io/gh/mgrl/photobooth-app/branch/dev/graph/badge.svg?token=SBB5DGX17V)](https://codecov.io/gh/mgrl/photobooth-app)

The photobooth app is written in Python 🐍 and coming along with a modern Vue frontend.

**[Installation](https://mgrl.github.io/photobooth-docs/installation/)** - **[Documentation](https://mgrl.github.io/photobooth-docs/)** - **[PyPI package](https://pypi.org/project/photobooth-app/)** - **[3d printed box](https://mgrl.github.io/photobooth-docs/photobox3dprint/)**

## 😍 Features

- 📹 camera live preview with shortest delay as possible, permanent video live view in background
- ⚡️ optimized for speed, live stream hardware accelerated on rpi, cpu load < 20%
- 🫶 several camera backends supported for high quality stills and livestream
- 💡 WLED support signaling photo countdown and feedback to the user when the photo is actually taken
- 🤝 Linux 🐧, Raspberry Pi 🍓 and Windows 🪟 platforms supported

## 📷 Supported Cameras

The photobooth app's Python backend allows to use different camera types on Linux and Windows platforms:

- Raspberry Pi Camera Module 1/2/3 (with or without autofocus)
- Arducam cameras (with or without autofocus)
- DSLR camera via
  - gphoto2, Linux
  - digicamcontrol, Windows (not yet implemented)
- webcams (via opencv2 or v4l)

The app controls camera's autofocus, handles led signaling when a photo is taken and streams live video to photobooth.

The reference photobooth box is made from 3d printed parts, [see the 3d printed reference box over here](https://mgrl.github.io/photobooth-docs/photobox3dprint/).

## 💅 Screenshots

![frontpage](https://raw.githubusercontent.com/mgrl/photobooth-app/main/screenshots/frontpage.png)
[Find more screenshots in the documentation](https://mgrl.github.io/photobooth-docs/screenshots)

## 🔧 Installation

[See separate installation instructions in the documentation](https://mgrl.github.io/photobooth-docs/installation/).

The photobooth app can be used standalone but is not feature complete yet.
Anyway, it integrates well with the fully blown [photobooth project](https://photoboothproject.github.io/),
see [description how to achieve integration](https://mgrl.github.io/photobooth-docs/reference/photoboothprojectintegration/).

## 📣 Changelog

see separate file:
<https://github.com/mgrl/photobooth-app/blob/main/CHANGELOG.md>

### ©️ License

The software is licensed under the MIT license.

### 🎉 Donation

If you like my work and like to keep me motivated you can sponsor me:

[![Donate](https://img.shields.io/badge/Donate-PayPal-green.svg)](https://www.paypal.com/donate/?hosted_button_id=8255Y566TBNEC)
