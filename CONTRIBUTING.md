# Contributing to photobooth-app

First off, thanks for taking the time to contribute! ❤️ All types of contributions are encouraged and valued. Read on for the different ways you can help and the process we follow to make reviewing and merging your work as smooth as possible.

---

## Table of Contents

- [Help Translate the App](#help-translate-the-app)  
- [Improve the Documentation](#improve-the-documentation)  
- [Report Bugs & Request Features](#report-bugs--request-features)  
- [Code Contribution](#code-contribution)  
  - [Prerequisites](#prerequisites)  
  - [Setting Up the Repo](#setting-up-the-repo)  
  - [Running & Testing Locally](#running--testing-locally)  
  - [Commercialization Code Contributions](#commercialization-code-contributions)  
  - [Submitting a Pull Request](#submitting-a-pull-request)  
- [Stay Connected](#stay-connected)  

---

## Help Translate the App

We use Crowdin’s automated pre-translation and need your help to proofread and improve it.

1. Visit the photobooth-app project on Crowdin.  
2. Select your language and click **Translate** or **Proofread**.  
3. Tackle untranslated or machine-translated strings and approve your fixes.  
4. Once the language reaches 100% translated and proofread, it ships in the next release.  
5. Drop a note in our Discussions to let us know you’ve contributed so we can celebrate!  

---

## Improve the Documentation

Our docs live in a separate repository:

- Fork and clone [photobooth-app/photobooth-docs](https://github.com/photobooth-app/photobooth-docs).  
- Make your edits or additions.  
- Submit a pull request—no contribution is too small, whether it’s fixing typos, reorganizing content, or adding new guides.  

---

## Report Bugs & Request Features

Even if you can’t code, you can help by:

- Searching existing [issues](https://github.com/photobooth-app/photobooth-app/issues) to avoid duplicates.  
- Opening a new issue with a clear title, reproduction steps, and expected behavior.  
- Voting on or commenting on existing issues/features to help us prioritize.  

---

## Code Contribution

### Prerequisites

- You must be the author of your contributions and grant the project license rights.  
- Install photobooth-app following the [official setup guide](https://photobooth-app.org/setup/installation/).  
- Have VS Code (or your favorite editor) installed.  
- [uv](https://github.com/uv-vscode/uv) for virtual-environment management.  


### Commercialization Code Contributions

The maintainers will not add or maintain any code specifically targeting commercialization within this open-source project. However, contributors are welcome to submit pull requests that introduce commercial features or integrations under the following conditions:

- The code is well-architected, follows existing style and standards, and includes necessary tests.  
- The contribution is accompanied by clear documentation explaining its purpose, usage, and any licensing considerations.  
- The contributor agrees to take full responsibility for ongoing maintenance, updates, and compatibility of the commercial code.  
- Any security or license implications are clearly disclosed in the pull request description.  

Commercial code that meets these criteria may be merged into the main repository. If the contributor ceases maintenance or the code becomes a burden, the maintainers reserve the right to remove or deprecate the feature.  


### Setting Up the Repo

```bash
git clone https://github.com/photobooth-app/photobooth-app.git
cd photobooth-app

uv venv --system-site-packages     # allows access to libcamera/picamera2
uv sync                            # install dependencies
```

### Running & Testing Locally

```bash
uv run photobooth
```

- The app reloads on each run.  
- For front-end changes, follow the [frontend setup instructions](https://github.com/photobooth-app/photobooth-frontend).  

### Submitting a Pull Request

1. Create a feature branch (`git checkout -b feature/my-feature`).  
2. Commit your changes with clear, descriptive messages.  
3. Push to your fork and open a PR against `main`.  
4. Fill out the PR template—link to related issue(s), describe your changes, and any testing steps.  
5. Respond to review feedback promptly to help us merge faster.  

---

## Stay Connected

Even if you don’t code, you can still support us:

- Star ⭐ the repo  
- Share on social media or in your blog  
- Tell your friends and colleagues about photobooth-app  

Thank you for making photobooth-app better! 🎉