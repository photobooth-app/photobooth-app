"""
Testing virtual camera Backend
"""

import logging
import os
from unittest.mock import patch

import pytest

logger = logging.getLogger(name=None)


def test_app():
    import photobooth.application

    photobooth.application._create_app()


def test_main_instance():
    from photobooth.__main__ import main

    main(run_server=False)


def test_main_instance_create_dirs_permission_error():
    from photobooth.application import _create_basic_folders

    with patch.object(os, "makedirs", side_effect=RuntimeError("effect: failed creating folder")):
        # emulate write access issue and ensure an exception is received to make the app fail starting.
        with pytest.raises(RuntimeError):
            _create_basic_folders()


def test_main_instance_create_dirs_permission_error_reraisesandabortsstart():
    import photobooth.application

    with patch.object(os, "makedirs", side_effect=RuntimeError("effect: failed creating folder")):
        # emulate write access issue and ensure an exception is received to make the app fail starting.
        with pytest.raises(RuntimeError):
            photobooth.application._create_app()
