"""
Testing Simulated Backend
"""
import logging
import socket

import pytest

logger = logging.getLogger(name=None)


# TODO: this modifies the main variable -> tests stop logging afterwards due to shutdown ressources
def test_main_package():
    from photobooth import __main__

    __main__.main(False)


def test_singleinstance():
    from photobooth import __main__

    # bind fails on second instance, pretend we have an instance here:
    s = socket.socket()
    s.bind(("localhost", 19988))

    with pytest.raises(SystemExit):
        __main__.main(False)

    s.close()
