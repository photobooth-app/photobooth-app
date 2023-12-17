import logging
from unittest.mock import patch

import psutil
import pytest

from photobooth.containers import ApplicationContainer
from photobooth.services.containers import ServicesContainer

logger = logging.getLogger(name=None)


@pytest.fixture()
def services() -> ServicesContainer:
    # setup
    application_container = ApplicationContainer()

    services = application_container.services()

    # deliver
    yield services
    services.shutdown_resources()


def test_filetransfer_service_disabled(services: ServicesContainer):
    """service is disabled by default - test for that."""

    # init when called
    _ = services.filetransfer_service()

    # nothing to check here...
    assert True


def test_filetransfer_service_enabled(services: ServicesContainer):
    """service is disabled by default - test for that."""

    services.config().filetransfer.enabled = True

    # init when called
    filetransfer_service = services.filetransfer_service()

    # check that worker_thread came up.
    assert filetransfer_service._worker_thread.is_alive() is True


def test_filetransfer_handle_unmount(services: ServicesContainer):
    """service is disabled by default - test for that."""

    services.config().filetransfer.enabled = True

    # init when called
    filetransfer_service = services.filetransfer_service()

    filetransfer_service.handle_unmount(psutil.disk_partitions()[-1])


@patch("shutil.copytree")
def test_filetransfer_handle_mount(mock_copytree, services: ServicesContainer):
    """service is disabled by default - test for that."""

    services.config().filetransfer.enabled = True

    # init when called
    filetransfer_service = services.filetransfer_service()

    filetransfer_service.handle_mount(psutil.disk_partitions()[-1])

    # check shutil.copytree was invoked
    mock_copytree.assert_called()


@patch("shutil.copytree")
def test_filetransfer_handle_mount_no_target_name(mock_copytree, services: ServicesContainer):
    """service is disabled by default - test for that."""

    services.config().filetransfer.enabled = True
    services.config().filetransfer.target_folder_name = ""

    # init when called
    filetransfer_service = services.filetransfer_service()

    filetransfer_service.handle_mount(psutil.disk_partitions()[-1])

    # check shutil.copytree was invoked
    assert not mock_copytree.called
