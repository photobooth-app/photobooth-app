"""
Testing exceptions in backends
"""
import logging
from unittest import mock
from unittest.mock import patch

import pytest

from photobooth.container import Container, container
from photobooth.services.aquisitionservice import AquisitionService
from photobooth.services.config import appconfig
from photobooth.services.informationservice import InformationService
from photobooth.services.sseservice import SseService

logger = logging.getLogger(name=None)


@pytest.fixture(autouse=True)
def run_around_tests():
    appconfig.reset_defaults()

    yield


# need fixture on module scope otherwise tests fail because GPIO lib gets messed up
@pytest.fixture(scope="module")
def _container() -> Container:
    # setup
    container.start()

    # deliver
    yield container
    container.stop()


def test_infoservice_init_exceptions(_container: Container):
    error_mock = mock.MagicMock()
    error_mock.side_effect = Exception("mock error")

    with patch.object(InformationService, "__init__", error_mock):
        try:
            _ = InformationService(SseService(), AquisitionService(SseService))
        except Exception as exc:
            raise AssertionError(f"'information_service' raised an exception, but it should fail in silence {exc}") from exc


def test_infoservice_start_exceptions(_container: Container):
    error_mock = mock.MagicMock()
    error_mock.side_effect = Exception("mock error")

    with patch.object(InformationService, "start", error_mock):
        try:
            infoservice = InformationService(SseService(), AquisitionService(SseService))
            infoservice.start()
        except Exception as exc:
            raise AssertionError(f"'information_service' raised an exception, but it should fail in silence {exc}") from exc


def test_infoservice_stop_exceptions(_container: Container):
    error_mock = mock.MagicMock()
    error_mock.side_effect = Exception("mock error")

    with patch.object(InformationService, "stop", error_mock):
        try:
            infoservice = InformationService(SseService(), AquisitionService(SseService))
            infoservice.stop()
            infoservice = InformationService(SseService(), AquisitionService(SseService))
            infoservice.start()
            infoservice.stop()
        except Exception as exc:
            raise AssertionError(f"'information_service' raised an exception, but it should fail in silence {exc}") from exc
