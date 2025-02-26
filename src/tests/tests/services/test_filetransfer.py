import logging
from collections.abc import Generator
from unittest.mock import patch

import psutil
import pytest

from photobooth.appconfig import appconfig
from photobooth.container import Container, container

logger = logging.getLogger(name=None)


@pytest.fixture(scope="module")
def _container() -> Generator[Container, None, None]:
    # setup
    container.start()

    # deliver
    yield container
    container.stop()


def test_filetransfer_service_disabled(_container: Container):
    """service is disabled by default - test for that."""

    # init when called
    _ = _container.filetransfer_service.start()

    # nothing to check here...
    assert True


def test_filetransfer_service_enabled(_container: Container):
    """service is disabled by default - test for that."""

    appconfig.filetransfer.enabled = True
    _container.filetransfer_service.stop()
    _container.filetransfer_service.start()

    assert _container.filetransfer_service._worker_thread
    # check that worker_thread came up.
    assert _container.filetransfer_service._worker_thread.is_alive() is True


def test_filetransfer_handle_unmount(_container: Container):
    """service is disabled by default - test for that."""

    appconfig.filetransfer.enabled = True

    _container.filetransfer_service.stop()
    _container.filetransfer_service.start()

    _container.filetransfer_service.handle_unmount(psutil.disk_partitions()[-1])


@patch("shutil.copytree")
def test_filetransfer_handle_mount(mock_copytree, _container: Container):
    """service is disabled by default - test for that."""

    appconfig.filetransfer.enabled = True

    _container.filetransfer_service.stop()
    _container.filetransfer_service.start()

    _container.filetransfer_service.handle_mount(psutil.disk_partitions()[-1])

    # check shutil.copytree was invoked
    mock_copytree.assert_called()


@patch("shutil.copytree")
def test_filetransfer_handle_mount_no_target_name(mock_copytree, _container: Container):
    """service is disabled by default - test for that."""

    appconfig.filetransfer.enabled = True
    appconfig.filetransfer.target_folder_name = ""

    _container.filetransfer_service.stop()
    _container.filetransfer_service.start()

    _container.filetransfer_service.handle_mount(psutil.disk_partitions()[-1])

    # check shutil.copytree was invoked
    assert not mock_copytree.called
