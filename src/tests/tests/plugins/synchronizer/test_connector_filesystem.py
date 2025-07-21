import logging
from pathlib import Path

import pytest

from photobooth.plugins.synchronizer.connectors.filesystem import FilesystemConnector, FilesystemConnectorConfig

logger = logging.getLogger(name=None)


@pytest.fixture()
def fs_backend(tmp_path):
    fs_backend = FilesystemConnector(
        FilesystemConnectorConfig(
            target_dir=tmp_path,
        )
    )

    yield fs_backend  # Run the test

    # Teardown
    if fs_backend.is_connected():
        fs_backend.disconnect()


def test_get_str(fs_backend: FilesystemConnector):
    assert fs_backend.__str__()


def test_connect_creates_target_dir(fs_backend: FilesystemConnector):
    assert fs_backend._target_dir
    testfolder = Path(fs_backend._target_dir, "anyother/folder/sub")
    fs_backend._target_dir = testfolder

    assert not testfolder.exists()

    fs_backend.connect()

    assert testfolder.is_dir()


def test_connect_check_for_valid_target_dir(fs_backend: FilesystemConnector):
    fs_backend._target_dir = None
    with pytest.raises(ValueError):
        fs_backend.connect()


def test_connect_check_for_existing_file_target_dir(fs_backend: FilesystemConnector):
    assert fs_backend._target_dir
    file_target = Path(fs_backend._target_dir, "filename")
    file_target.touch()
    fs_backend._target_dir = file_target

    with pytest.raises(ValueError):
        fs_backend.connect()

    assert fs_backend.is_connected() is False


def test_connect_disconnect(fs_backend: FilesystemConnector, tmp_path: Path):
    fs_backend.connect()
    assert fs_backend.is_connected()
    fs_backend.disconnect()
    # this backend cannot disconnect as long as the dir exists.
    assert fs_backend.is_connected() is True

    # is_connected=False if no dir as target...
    fs_backend._target_dir = Path(tmp_path, "nonexistent_anything")
    assert fs_backend.is_connected() is False


def test_upload_compare(fs_backend: FilesystemConnector):
    fs_backend.connect()
    assert fs_backend.is_connected()
    assert fs_backend._target_dir

    # step1: upload
    fs_backend.do_upload(Path("src/tests/assets/input_lores.jpg"), Path("subdir1/input_lores_uploaded.jpg"))
    assert Path(fs_backend._target_dir, "subdir1/input_lores_uploaded.jpg").is_file()

    # step2:  compare
    assert fs_backend.get_remote_samefile(Path("src/tests/assets/input_lores.jpg"), Path("subdir1/input_lores_uploaded.jpg"))


def test_upload_delete(fs_backend: FilesystemConnector):
    fs_backend.connect()
    assert fs_backend.is_connected()
    assert fs_backend._target_dir

    # step1: upload
    fs_backend.do_upload(Path("src/tests/assets/input_lores.jpg"), Path("subdir1/input_lores_uploaded.jpg"))
    assert Path(fs_backend._target_dir, "subdir1/input_lores_uploaded.jpg").is_file()

    # step2:  delete
    fs_backend.do_delete_remote(Path("subdir1/input_lores_uploaded.jpg"))
    assert Path(fs_backend._target_dir, "subdir1/input_lores_uploaded.jpg").is_file() is False


def test_compare_exceptions(fs_backend: FilesystemConnector):
    fs_backend.connect()
    assert fs_backend.is_connected()
    assert fs_backend._target_dir

    assert fs_backend.get_remote_samefile(Path("src/tests/assets/input_lores.jpg"), Path("subdir1/input_lores_nonexistent.jpg")) is False
    assert fs_backend.get_remote_samefile(Path("src/tests/assets/input_nonexistent.jpg"), Path("subdir1/input_lores_nonexistent.jpg")) is False
