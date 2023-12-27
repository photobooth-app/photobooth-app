"""
Testing main
"""

import logging
import socket
from importlib import reload

import pytest

import photobooth.services.config

reload(photobooth.services.config)  # reset config to defaults.
logger = logging.getLogger(name=None)


def test_singleinstance():
    from photobooth.__main__ import main

    # bind fails on second instance, pretend we have an instance here:
    s = socket.socket()
    s.bind(("localhost", 19988))

    with pytest.raises(SystemExit):
        main(False)

    s.close()


def test_main_instance():
    from photobooth.__main__ import main

    main(False)
