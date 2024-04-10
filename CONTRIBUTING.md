# 🚀 Contribute

## Help Improve

### Help Translate the App

[![Crowdin](https://badges.crowdin.net/photobooth-app/localized.svg)](https://crowdin.com/project/photobooth-app)

We use automated pre-translation powered by Crowdin.
Help to improve the accuracy by proofreading the translation.
It's very easy to translate and proofread the current translations:

- [Open the photobooth-app translation project in Crowdin](https://crowdin.com/project/photobooth-app/invite?h=b00f8c8abec20ed573058db633f2452c2057822).
- Click the dropdown button next to your language to open language details.
- Click the button "translate" or "proofread".
- Work through the items, improve the translation and click the check mark to approve.
- If the language is 100% translated and proofread, it will be included in the next release.
- Leave a short notice in the discussions that you improved the translation to let us know. Thank you!

### Post Issues

If you find an issue, please post it in the [photobooth app issue tracker](https://github.com/photobooth-app/photobooth-app/issues).

### Improve Documentation

If you find an issue in the documentation, [modify the documentation](https://github.com/photobooth-app/photobooth-docs) or open a [discussion](https://github.com/photobooth-app/photobooth-app/discussions).

### Send Patches via Pull Request

Feel free to [fork the app](https://github.com/photobooth-app/photobooth-app), improve the software and send a pull request.
For questions use the github discussions or issue tracker.

## Help Develop

### Guidelines

- Implementation shall be platform agnostic (Linux and Windows).
- If possible avoid additional dependencies.

### Install development version

Stable releases are published at [PyPI registry](https://pypi.org/project/photobooth-app/) usually.
To test the latest development version install directly from git:

```sh
pip install git+https://github.com/photobooth-app/photobooth-app.git@dev
```

### Development

Develop on Windows or Linux using VScode.
Dependency management is realized using poetry.

To get started on working on the backend:

- First install pdm: `pip install pdm`
- Install further dependencies:
  - `sudo apt-get install libturbojpeg` - In this case for Ubuntu based systems
  - `pip install uvicorn`
  - `pip install dependency-injector`
  
- Then install all the requirements: `pdm install`
- Build with `pdm build`
- Start with `pdm run python -m photobooth`

Additional requirements for frontend development
    - nodejs 16 (nodejs 18 fails proxying the devServer)
    - yarn
    - quasar cli <https://quasar.dev/start/quasar-cli>

### Automated Testing

Tests are run via Github Actions.
The tests run in the Cloud on hosted Github runners as well as on a self-hosted runner for hardware testing.
[Coverage](https://app.codecov.io/gh/photobooth-app/photobooth-app) is reported to codecov.

#### Selfhosted Github Runner

Supports additional tests for hardware:

- Raspberry Pi Camera Module 3 connected to test picamera2 and autofocus algorithms
- WLED module is connected to test LED effects on thrill and shoot
- gphoto2 is installed with virtual ptp device
  - install latest dev with gphoto2 updater,  modify configure command as described here <https://github.com/gphoto/libgphoto2/issues/408>)
  - add photos libgphoto provides when capture is requested to /usr/share/local/libgphoto2_port/xxxversion/vcamera/
- webcamera is connected to test cv2 and v4l backends
