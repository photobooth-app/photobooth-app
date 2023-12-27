"""
Testing exceptions in backends
"""
import logging
from importlib import reload
from unittest import mock
from unittest.mock import patch

import pytest

import photobooth.services.config
from photobooth.containers import ApplicationContainer
from photobooth.services.containers import ServicesContainer
from photobooth.services.informationservice import InformationService

reload(photobooth.services.config)  # reset config to defaults.
logger = logging.getLogger(name=None)


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
