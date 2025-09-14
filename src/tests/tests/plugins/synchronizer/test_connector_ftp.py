import logging
import os
import threading
import time
from ftplib import FTP
from pathlib import Path

import pyftpdlib
import pytest
from pydantic import SecretStr
from pyftpdlib.authorizers import DummyAuthorizer
from pyftpdlib.handlers import TLS_FTPHandler
from pyftpdlib.servers import ThreadedFTPServer

from photobooth.plugins.synchronizer.connectors.ftp import FtpConnector, FtpConnectorConfig

logger = logging.getLogger(name=None)


@pytest.fixture()
def ftp_server(tmp_path):
    cwd_orig = os.getcwd()
    # add demo-tls security for testing, ref https://pyftpdlib.readthedocs.io/en/latest/tutorial.html#ftps-ftp-over-tls-ssl-server
    CERTFILE = os.path.abspath(os.path.join(str(pyftpdlib.__path__[0]), "test", "keycert.pem"))

    # Setup: configure and start the FTP server in a thread
    authorizer = DummyAuthorizer()
    authorizer.add_user("testuser", "testpass", homedir=tmp_path, perm="elradfmwT")

    handler = TLS_FTPHandler
    handler.certfile = CERTFILE  # type: ignore
    handler.authorizer = authorizer

    server = ThreadedFTPServer(("127.0.0.1", 2121), handler)

    thread = threading.Thread(target=server.serve_forever, kwargs={"handle_exit": False}, daemon=True)
    thread.start()
    time.sleep(0.1)  # Allow server to start

    yield server  # Run the test

    # Teardown
    server.close_all()

    # ftplibd issue: https://github.com/giampaolo/pyftpdlib/pull/661
    os.chdir(cwd_orig)


@pytest.fixture()
def ftp_backend():
    ftp_backend = FtpConnector(
        FtpConnectorConfig(
            host="127.0.0.1",
            port=2121,
            username="testuser",
            password=SecretStr("testpass"),
            secure=False,
        )
    )

    yield ftp_backend  # Run the test

    # Teardown
    if ftp_backend.is_connected():
        ftp_backend.disconnect()


def test_get_str(ftp_backend: FtpConnector):
    assert ftp_backend.__str__()


def test_ftp_login(ftp_server):
    # just test the server itself is working fine...
    ftp = FTP()
    ftp.connect("127.0.0.1", 2121)
    ftp.login("testuser", "testpass")
    assert ftp.pwd() == "/"
    ftp.quit()


def test_connect_check_no_empty_host(ftp_server, ftp_backend: FtpConnector):
    ftp_backend._host = ""
    with pytest.raises(ValueError):
        ftp_backend.connect()

    assert ftp_backend.is_connected() is False


def test_noconnect_ensureconnected(ftp_server, ftp_backend: FtpConnector):
    ftp_backend._ensure_connected()
    assert ftp_backend.is_connected()


def test_connect_disconnect(ftp_server, ftp_backend: FtpConnector):
    ftp_backend.connect()
    assert ftp_backend.is_connected()
    ftp_backend.disconnect()
    assert ftp_backend.is_connected() is False


def test_connect_force_secure(ftp_server, ftp_backend: FtpConnector):
    ftp_backend._secure = True
    ftp_backend.connect()
    assert ftp_backend.is_connected()


def test_connect_force_nosecure(ftp_server, ftp_backend: FtpConnector):
    ftp_backend._secure = False
    ftp_backend.connect()
    assert ftp_backend.is_connected()


def test_disconnect_already_disconnected_raises_nothing(ftp_server, ftp_backend: FtpConnector):
    ftp_backend.connect()
    assert ftp_backend.is_connected()
    assert ftp_backend._ftp
    ftp_backend._ftp.quit()  # directly close the connection, which will provoke an err on subseq disconnect cmd
    ftp_backend.disconnect()  # does not raise an error
    assert ftp_backend.is_connected() is False


def test_connect_check_host_down(ftp_server, ftp_backend: FtpConnector):
    ftp_backend.connect()
    assert ftp_backend.is_connected()
    ftp_server.close_all()
    assert ftp_backend.is_connected() is False


def test_upload_compare(ftp_server, ftp_backend: FtpConnector):
    ftp_backend.connect()
    assert ftp_backend.is_connected()
    server_home_dir = ftp_server.handler.authorizer.get_home_dir("testuser")

    # step1: upload
    ftp_backend.do_upload(Path(__file__).parent.joinpath("../../../assets/input_lores.jpg").resolve(), Path("subdir1/input_lores_uploaded.jpg"))
    assert Path(server_home_dir, "subdir1/input_lores_uploaded.jpg").is_file()

    # step2:  compare
    assert ftp_backend.do_check_issame(Path("src/tests/assets/input_lores.jpg"), Path("subdir1/input_lores_uploaded.jpg"))


def test_compare_exceptions(ftp_server, ftp_backend: FtpConnector):
    ftp_backend.connect()
    assert ftp_backend.is_connected()

    assert (
        ftp_backend.do_check_issame(Path(__file__).parent.joinpath("../../../assets/input_lores.jpg").resolve(), Path("input_lores_nonexistent.jpg"))
        is False
    )
    assert ftp_backend.do_check_issame(Path("src/tests/assets/input_nonexistent.jpg"), Path("subdir1/input_lores_nonexistent.jpg")) is False


def test_upload_delete(ftp_server, ftp_backend: FtpConnector):
    ftp_backend.connect()
    assert ftp_backend.is_connected()
    server_home_dir = ftp_server.handler.authorizer.get_home_dir("testuser")

    # step1: upload
    ftp_backend.do_upload(Path(__file__).parent.joinpath("../../../assets/input_lores.jpg").resolve(), Path("subdir1/input_lores_uploaded.jpg"))
    assert Path(server_home_dir, "subdir1/input_lores_uploaded.jpg").is_file()

    # step2:  delete
    ftp_backend.do_delete_remote(Path("subdir1/input_lores_uploaded.jpg"))
    assert Path(server_home_dir, "subdir1/input_lores_uploaded.jpg").is_file() is False
