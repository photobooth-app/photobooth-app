# 🚀 Contribute

## Help Improve

### Post Issues

If you find an issue, please post it in the [photobooth app issue tracker](https://github.com/mgrl/photobooth-app/issues).

### Improve Documentation

If you find an issue in the documentation, [modify the documentation](https://github.com/mgrl/photobooth-docs) or open a [discussion](https://github.com/mgrl/photobooth-app/discussions).

### Send Patches via Pull Request

Feel free to [fork the app](https://github.com/mgrl/photobooth-app), improve the software and send a pull request.
For questions use the github discussions or issue tracker.

## Help Develop

### Install development version

Stable releases are published at [PyPI registry](https://pypi.org/project/photobooth-app/) usually.
To test the latest development version install directly from git:

```sh
pip install git+https://github.com/mgrl/photobooth-app.git@dev
```

### Development

Develop on Windows or Linux using VScode.
Dependency management is realized using poetry.

Additional requirements for frontend development
    - nodejs 16 (nodejs 18 fails proxying the devServer)
    - yarn
    - quasar cli <https://quasar.dev/start/quasar-cli>

### Automated Testing

Tests are run via Github Actions.
The tests run in the Cloud on hosted Github runners as well as on a self-hosted runner for hardware testing.
[Coverage](https://app.codecov.io/gh/mgrl/photobooth-app) is reported to codecov.

#### Selfhosted Github Runner

Supports additional tests for hardware:

- Raspberry Pi Camera Module 3 connected to test picamera2 and autofocus algorithms
- WLED module is connected to test LED effects on thrill and shoot
- gphoto2 is installed with virtual ptp device
    - install latest dev with gphoto2 updater,  modify configure command as described here <https://github.com/gphoto/libgphoto2/issues/408>)
    - add photos libgphoto provides when capture is requested to /usr/share/local/libgphoto2_port/xxxversion/vcamera/
- webcamera is connected to test cv2 and v4l backends
