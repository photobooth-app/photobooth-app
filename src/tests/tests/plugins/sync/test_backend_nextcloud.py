import logging
from pathlib import Path
from uuid import uuid4

import pytest
from nc_py_api import NextcloudException
from pydantic import SecretStr

from photobooth.plugins.synchronizer.backends.nextcloud import NextcloudBackend, NextcloudBackendConfig

logger = logging.getLogger(name=None)


@pytest.fixture()
def nextcloud_backend():
    nextcloud_backend = NextcloudBackend(
        NextcloudBackendConfig(
            url="http://127.0.0.1:8083",
            username="testuser",
            password=SecretStr("testpass"),
            target_dir=str(uuid4()),
        )
    )

    yield nextcloud_backend  # Run the test

    # Teardown
    if nextcloud_backend.is_connected():
        nextcloud_backend.disconnect()


def test_connect_check_no_empty_host(nextcloud_backend: NextcloudBackend):
    nextcloud_backend._url = ""
    with pytest.raises(ValueError):
        nextcloud_backend.connect()

    assert nextcloud_backend.is_connected() is False


def test_connect_disconnect(nextcloud_backend: NextcloudBackend):
    nextcloud_backend.connect()
    assert nextcloud_backend.is_connected()
    nextcloud_backend.disconnect()
    # since the client is kind of stateless, disconnecting has no effect anyways...
    assert nextcloud_backend.is_connected() is True


def test_upload_compare(nextcloud_backend: NextcloudBackend):
    nextcloud_backend.connect()
    assert nextcloud_backend.is_connected()

    with pytest.raises(NextcloudException):
        nextcloud_backend.nc.files.by_path(str(nextcloud_backend._target_dir.joinpath("subdir1/input_lores_uploaded.jpg")))

    # step1: upload
    nextcloud_backend.do_upload(Path("src/tests/assets/input_lores.jpg"), Path("subdir1/input_lores_uploaded.jpg"))
    assert nextcloud_backend.nc.files.by_path(str(nextcloud_backend._target_dir.joinpath("subdir1/input_lores_uploaded.jpg"))) is not None

    # step2:  compare
    assert nextcloud_backend.get_remote_samefile(Path("src/tests/assets/input_lores.jpg"), Path("subdir1/input_lores_uploaded.jpg"))


def test_compare_exceptions(nextcloud_backend: NextcloudBackend):
    nextcloud_backend.connect()
    assert nextcloud_backend.is_connected()

    assert nextcloud_backend.get_remote_samefile(Path("src/tests/assets/input_lores.jpg"), Path("input_lores_nonexistent.jpg")) is False
    assert nextcloud_backend.get_remote_samefile(Path("src/tests/assets/input_nonexistent.jpg"), Path("subdir1/input_lores_nonexistent.jpg")) is False


def test_upload_delete(nextcloud_backend: NextcloudBackend):
    nextcloud_backend.connect()
    assert nextcloud_backend.is_connected()
    # server_home_dir = ftp_server.handler.authorizer.get_home_dir("testuser")

    # step1: upload
    nextcloud_backend.do_upload(Path("src/tests/assets/input_lores.jpg"), Path("subdir1/input_lores_uploaded.jpg"))
    # assert Path(server_home_dir, "subdir1/input_lores_uploaded.jpg").is_file()

    # step2:  delete
    nextcloud_backend.do_delete_remote(Path("subdir1/input_lores_uploaded.jpg"))
    # assert Path(server_home_dir, "subdir1/input_lores_uploaded.jpg").is_file() is False
