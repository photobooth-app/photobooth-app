import logging
import threading
import time
from ftplib import FTP

import pytest
from pydantic import SecretStr
from pyftpdlib.authorizers import DummyAuthorizer
from pyftpdlib.handlers import FTPHandler
from pyftpdlib.servers import ThreadedFTPServer

from photobooth.plugins.synchronizer.config import Common, FilesystemConfigGroup, FtpServerConfigGroup, SynchronizerConfig
from photobooth.plugins.synchronizer.synchronizer import Synchronizer

logger = logging.getLogger(name=None)


@pytest.fixture()
def synchronizer_plugin():
    # setup
    shrftp = Synchronizer()

    shrftp._config = SynchronizerConfig(
        common=Common(
            enabled=True,
        ),
        ftp_server=FtpServerConfigGroup(
            host="127.0.0.1",
            port=2121,
            username="testuser",
            password=SecretStr("testpass"),
            secure=False,
        ),
        filesystem=FilesystemConfigGroup(
            target_dir="/tmp/test123",
        ),
    )

    yield shrftp


@pytest.fixture()
def ftp_server(tmp_path):
    # Setup: configure and start the FTP server in a thread
    authorizer = DummyAuthorizer()
    authorizer.add_user("testuser", "testpass", homedir=tmp_path, perm="elradfmwT")

    handler = FTPHandler
    handler.authorizer = authorizer

    server = ThreadedFTPServer(("127.0.0.1", 2121), handler)

    thread = threading.Thread(target=server.serve_forever, kwargs={"handle_exit": False}, daemon=True)
    thread.start()
    # time.sleep(0.1)  # Allow server to start

    yield  # Run the test

    # Teardown
    server.close_all()


def test_ftp_login(ftp_server):
    # just test the server itself is working fine...
    ftp = FTP()
    ftp.connect("127.0.0.1", 2121)
    ftp.login("testuser", "testpass")
    assert ftp.pwd() == "/"
    ftp.quit()


def test_init(ftp_server, synchronizer_plugin: Synchronizer):
    synchronizer_plugin.start()

    time.sleep(1)

    synchronizer_plugin.stop()
