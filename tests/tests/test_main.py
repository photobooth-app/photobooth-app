"""
Testing main
"""

import logging
import os
from unittest.mock import patch

import pytest

logger = logging.getLogger(name=None)


def test_main_instance():
    from photobooth.__main__ import main

    main(False)


def test_main_instance_create_dirs_permission_error():
    from photobooth.__main__ import main

    with patch.object(os, "makedirs", side_effect=RuntimeError("effect: failed creating folder")):
        # emulate write access issue and ensure an exception is received to make the app fail starting.
        with pytest.raises(RuntimeError):
            main(False)
