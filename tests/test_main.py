"""
Testing Simulated Backend
"""
import logging
import socket

import pytest
import uvicorn

from photobooth.appconfig import AppConfig

logger = logging.getLogger(name=None)


def test_main_package():
    from photobooth import __main__

    server = __main__.main()
    assert isinstance(server, uvicorn.Server)


def test_singleinstance():
    from photobooth import __main__

    # bind fails on second instance, pretend we have an instance here:
    s = socket.socket()
    s.bind((AppConfig().common.webserver_bind_ip, AppConfig().common.webserver_port))

    with pytest.raises(SystemExit):
        __main__.guard(AppConfig().common.webserver_bind_ip, AppConfig().common.webserver_port)

    s.close()
