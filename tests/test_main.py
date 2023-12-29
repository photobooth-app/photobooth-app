"""
Testing main
"""

import logging
import socket

import pytest

from photobooth.services.config import appconfig


@pytest.fixture(autouse=True)
def run_around_tests():
    appconfig.reset_defaults()

    yield


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
