import logging
import os
from unittest.mock import patch

import pytest

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
