"""
Testing exceptions in backends
"""
import logging
from unittest import mock
from unittest.mock import patch

import pytest
from dependency_injector import providers

from photobooth.appconfig import AppConfig
from photobooth.containers import ApplicationContainer
from photobooth.services.backends.containers import BackendsContainer
from photobooth.services.backends.virtualcamera import VirtualCameraBackend
from photobooth.services.containers import ServicesContainer
from photobooth.services.informationservice import InformationService

logger = logging.getLogger(name=None)


@pytest.fixture()
def backends() -> BackendsContainer:
    # setup
    backends_container = BackendsContainer(
        config=providers.Singleton(AppConfig),
    )
    # deliver
    yield backends_container


def test_simulated_init_exceptions(backends: BackendsContainer):
    error_mock = mock.MagicMock()
    error_mock.side_effect = Exception("mock error")

    with patch.object(VirtualCameraBackend, "__init__", error_mock):
        try:
            backends.virtualcamera_backend()
        except Exception as exc:
            raise AssertionError(f"'simulated_backend' raised an exception, but it should fail in silence {exc}") from exc


def test_simulated_start_exceptions(backends: BackendsContainer):
    error_mock = mock.MagicMock()
    error_mock.side_effect = Exception("mock error")

    with patch.object(VirtualCameraBackend, "start", error_mock):
        try:
            backends.virtualcamera_backend()
        except Exception as exc:
            raise AssertionError(f"'simulated_backend' raised an exception, but it should fail in silence {exc}") from exc


def test_simulated_stop_exceptions(backends: BackendsContainer):
    error_mock = mock.MagicMock()
    error_mock.side_effect = Exception("mock error")

    with patch.object(VirtualCameraBackend, "stop", error_mock):
        try:
            backends.virtualcamera_backend()
            backends.shutdown_resources()

        except Exception as exc:
            raise AssertionError(f"'simulated_backend' raised an exception, but it should fail in silence {exc}") from exc


@pytest.fixture()
def services() -> ServicesContainer:
    # setup
    application_container = ApplicationContainer()

    services = application_container.services()

    # deliver
    yield services
    services.shutdown_resources()


def test_infoservice_init_exceptions(services: ServicesContainer):
    error_mock = mock.MagicMock()
    error_mock.side_effect = Exception("mock error")

    with patch.object(InformationService, "__init__", error_mock):
        try:
            services.information_service()
        except Exception as exc:
            raise AssertionError(f"'information_service' raised an exception, but it should fail in silence {exc}") from exc


def test_infoservice_start_exceptions(services: ServicesContainer):
    error_mock = mock.MagicMock()
    error_mock.side_effect = Exception("mock error")

    with patch.object(InformationService, "start", error_mock):
        try:
            services.information_service()
        except Exception as exc:
            raise AssertionError(f"'information_service' raised an exception, but it should fail in silence {exc}") from exc


def test_infoservice_stop_exceptions(services: ServicesContainer):
    error_mock = mock.MagicMock()
    error_mock.side_effect = Exception("mock error")

    with patch.object(InformationService, "stop", error_mock):
        try:
            services.information_service()
            services.shutdown_resources()
        except Exception as exc:
            raise AssertionError(f"'information_service' raised an exception, but it should fail in silence {exc}") from exc
