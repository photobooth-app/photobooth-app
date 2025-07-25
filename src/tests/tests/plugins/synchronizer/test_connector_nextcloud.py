import logging
from pathlib import Path
from uuid import uuid4

import pytest
import requests
from nc_py_api import NextcloudException
from pydantic import SecretStr

from photobooth.plugins.synchronizer.connectors.nextcloud import NextcloudConnector, NextcloudConnectorConfig

logger = logging.getLogger(name=None)

TEST_URL = "http://127.0.0.1:8083"


try:
    r = requests.get(TEST_URL, allow_redirects=False)
    r.raise_for_status()
except Exception:
    pytest.skip("no nextcloud service found, skipping tests", allow_module_level=True)


@pytest.fixture()
def nextcloud_backend():
    nextcloud_backend = NextcloudConnector(
        NextcloudConnectorConfig(
            url=TEST_URL,
            username="testuser",
            password=SecretStr("testpass"),
            target_dir=str(uuid4()),
        )
    )

    yield nextcloud_backend  # Run the test

    # Teardown
    if nextcloud_backend.is_connected():
        nextcloud_backend.disconnect()


def test_get_str(nextcloud_backend: NextcloudConnector):
    assert nextcloud_backend.__str__()


def test_connect_check_no_empty_host(nextcloud_backend: NextcloudConnector):
    nextcloud_backend._url = ""
    with pytest.raises(ValueError):
        nextcloud_backend.connect()

    assert nextcloud_backend.is_connected() is False


def test_connect_check_nonexistent_host(nextcloud_backend: NextcloudConnector):
    nextcloud_backend.connect()

    # destroy the instance to provoke exception
    nextcloud_backend.nc = None

    assert nextcloud_backend.is_connected() is False


def test_connect_check_disconnected(nextcloud_backend: NextcloudConnector):
    # destroy the instance to provoke exception
    nextcloud_backend._url = TEST_URL + "/illegalnonexistant/"
    nextcloud_backend.connect()

    assert nextcloud_backend.is_connected() is False


def test_connect_disconnect(nextcloud_backend: NextcloudConnector):
    nextcloud_backend.connect()
    assert nextcloud_backend.is_connected()
    nextcloud_backend.disconnect()
    # since the client is kind of stateless, disconnecting has no effect anyways...
    assert nextcloud_backend.is_connected() is True


def test_upload_compare(nextcloud_backend: NextcloudConnector):
    nextcloud_backend.connect()
    assert nextcloud_backend.is_connected()
    assert nextcloud_backend.nc

    with pytest.raises(NextcloudException):
        nextcloud_backend.nc.files.by_path(str(nextcloud_backend._target_dir.joinpath("subdir1/input_lores_uploaded.jpg")))

    # step1: upload
    nextcloud_backend.do_upload(Path("src/tests/assets/input_lores.jpg"), Path("subdir1/input_lores_uploaded.jpg"))
    assert nextcloud_backend.nc.files.by_path(str(nextcloud_backend._target_dir.joinpath("subdir1/input_lores_uploaded.jpg"))) is not None

    # step2:  compare
    assert nextcloud_backend.get_remote_samefile(Path("src/tests/assets/input_lores.jpg"), Path("subdir1/input_lores_uploaded.jpg"))


def test_compare_exceptions(nextcloud_backend: NextcloudConnector):
    nextcloud_backend.connect()
    assert nextcloud_backend.is_connected()

    assert nextcloud_backend.get_remote_samefile(Path("src/tests/assets/input_lores.jpg"), Path("input_lores_nonexistent.jpg")) is False
    assert nextcloud_backend.get_remote_samefile(Path("src/tests/assets/input_nonexistent.jpg"), Path("subdir1/input_lores_nonexistent.jpg")) is False


def test_upload_delete(nextcloud_backend: NextcloudConnector):
    nextcloud_backend.connect()
    assert nextcloud_backend.is_connected()
    assert nextcloud_backend.nc

    # step1: upload
    nextcloud_backend.do_upload(Path("src/tests/assets/input_lores.jpg"), Path("subdir2/input_lores_uploaded.jpg"))
    assert nextcloud_backend.nc.files.by_path(str(nextcloud_backend._target_dir.joinpath("subdir2/input_lores_uploaded.jpg"))) is not None

    # step2:  delete
    nextcloud_backend.do_delete_remote(Path("subdir2/input_lores_uploaded.jpg"))
    with pytest.raises(NextcloudException):
        nextcloud_backend.nc.files.by_path(str(nextcloud_backend._target_dir.joinpath("subdir2/input_lores_uploaded.jpg")))
