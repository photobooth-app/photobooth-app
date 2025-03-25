import logging
import os
from pathlib import Path
from unittest.mock import patch

import pytest

from photobooth import USERDATA_PATH

logger = logging.getLogger(name=None)


def test_main_instance_create_dirs_permission_error():
    from photobooth import _create_basic_folders

    with patch.object(os, "makedirs", side_effect=RuntimeError("effect: failed creating folder")):
        # emulate write access issue and ensure an exception is received to make the app fail starting.
        with pytest.raises(RuntimeError):
            _create_basic_folders()


def test_main_instance_create_dirs_permission_errorreraised_stops_starting_app():
    with patch.object(os, "makedirs", side_effect=PermissionError("effect: failed creating folder")):
        # emulate write access issue and ensure an exception is received to make the app fail starting.
        with pytest.raises(RuntimeError):
            __import__("photobooth.__init__")


def test_init_error_if_demoassets_is_no_symlink():
    target = Path(USERDATA_PATH, "demoassets")
    target.unlink(missing_ok=True)

    target.touch()
    assert target.is_file()

    with pytest.raises(RuntimeError):
        __import__("photobooth.__init__")

    target.unlink(missing_ok=False)


def test_init_userdata_after_init_there_is_demoassets_symlink():
    target = Path(USERDATA_PATH, "demoassets")
    target.unlink(missing_ok=True)

    # starting the app creates the symlink
    __import__("photobooth.__init__")

    if os.name == "nt":
        assert target.is_junction()
    else:
        assert target.is_symlink()
