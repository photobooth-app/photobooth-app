<!-- omit in toc -->
# Contributing to photobooth-app

First off, thanks for taking the time to contribute! ❤️

All types of contributions are encouraged and valued. See below sections for different ways to help and details about how this project handles them. Please make sure to read the relevant section before making your contribution. It will make it a lot easier for us maintainers and smooth out the experience for all involved. The community looks forward to your contributions. 🎉

> And if you like the project, but just don't have time to contribute, that's fine. There are other easy ways to support the project and show your appreciation, which we would also be very happy about:
>
> - Star the project
> - Talk about it
> - Refer to this project in blog articles
> - Add your project to the show and tell section in the Github discussions.

## Ways to Contribute

### Help to Translate the App

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

### Improving The Documentation

Feel free to send pull request to the [documentation repository](https://github.com/photobooth-app/photobooth-docs)

### Code Contribution

> ### Legal Notice
>
> When contributing to this project, you must agree that you have authored 100% of the content, that you have the necessary rights to the content and that the content you contribute may be provided under the project license.

#### Prerequisites

- [photobooth-app installed](https://photobooth-app.org/setup/installation/)
- VS Code
- uv

#### Setup the repo

```sh
git clone https://github.com/photobooth-app/photobooth-app.git
cd photobooth-app

uv venv --system-site-packages # allow acces to system packages for libcamera/picamera2
uv sync
```

#### Start the App

```sh
uv run photobooth
```

#### Code

Now you should be able to code. The app needs to be restarted after code changes to get in effect.
If you need to change the frontend also, follow the [instructions to setup frontend development](https://github.com/photobooth-app/photobooth-frontend).

#### Send a Pull Request

Once finished the development, you can send a pull request to the repo.
