import logging
from ftplib import FTP
from pathlib import Path

import pytest
from pydantic import SecretStr

from photobooth.plugins.synchronizer.connectors.ftp import FtpConnector, FtpConnectorConfig

logger = logging.getLogger(name=None)

host = "127.0.0.1"
port = 2121
server_home_dir = "/run/ftp_docker/ftp/testuser/"

try:
    ftp = FTP()
    ftp.connect("127.0.0.1", 2121)
    ftp.quit()

except Exception:
    pytest.skip("no ftp service found, skipping tests", allow_module_level=True)


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


def test_ftp_login():
    # just test the server itself is working fine...
    ftp = FTP()
    ftp.connect("127.0.0.1", 2121)
    ftp.login("testuser", "testpass")
    assert ftp.pwd() == "/"
    ftp.quit()


def test_connect_check_no_empty_host(ftp_backend: FtpConnector):
    ftp_backend._host = ""
    with pytest.raises(ValueError):
        ftp_backend.connect()

    assert ftp_backend.is_connected() is False


def test_noconnect_ensureconnected(ftp_backend: FtpConnector):
    ftp_backend._ensure_connected()
    assert ftp_backend.is_connected()


def test_connect_disconnect(ftp_backend: FtpConnector):
    ftp_backend.connect()
    assert ftp_backend.is_connected()
    ftp_backend.disconnect()
    assert ftp_backend.is_connected() is False


# def test_connect_force_secure(ftp_backend: FtpConnector):
#     ftp_backend._secure = True
#     ftp_backend.connect()
#     assert ftp_backend.is_connected()


def test_connect_force_nosecure(ftp_backend: FtpConnector):
    ftp_backend._secure = False
    ftp_backend.connect()
    assert ftp_backend.is_connected()


def test_disconnect_already_disconnected_raises_nothing(ftp_backend: FtpConnector):
    ftp_backend.connect()
    assert ftp_backend.is_connected()
    assert ftp_backend._ftp
    ftp_backend._ftp.quit()  # directly close the connection, which will provoke an err on subseq disconnect cmd
    ftp_backend.disconnect()  # does not raise an error
    assert ftp_backend.is_connected() is False


def test_upload_compare(ftp_backend: FtpConnector):
    ftp_backend.connect()
    assert ftp_backend.is_connected()

    # step1: upload
    ftp_backend.do_upload(Path("src/tests/assets/input_lores.jpg"), Path("subdir1/input_lores_uploaded.jpg"))
    assert Path(server_home_dir, "subdir1/input_lores_uploaded.jpg").is_file()

    # step2:  compare
    assert ftp_backend.do_check_issame(Path("src/tests/assets/input_lores.jpg"), Path("subdir1/input_lores_uploaded.jpg"))


def test_compare_exceptions(ftp_backend: FtpConnector):
    ftp_backend.connect()
    assert ftp_backend.is_connected()

    assert ftp_backend.do_check_issame(Path("src/tests/assets/input_lores.jpg"), Path("input_lores_nonexistent.jpg")) is False
    assert ftp_backend.do_check_issame(Path("src/tests/assets/input_nonexistent.jpg"), Path("subdir1/input_lores_nonexistent.jpg")) is False


def test_upload_delete(ftp_backend: FtpConnector):
    ftp_backend.connect()
    assert ftp_backend.is_connected()

    # step1: upload
    ftp_backend.do_upload(Path("src/tests/assets/input_lores.jpg"), Path("subdir1/input_lores_uploaded.jpg"))
    assert Path(server_home_dir, "subdir1/input_lores_uploaded.jpg").is_file()

    # step2:  delete
    ftp_backend.do_delete_remote(Path("subdir1/input_lores_uploaded.jpg"))
    assert Path(server_home_dir, "subdir1/input_lores_uploaded.jpg").is_file() is False
