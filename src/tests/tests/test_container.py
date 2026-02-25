"""
Testing exceptions in backends
"""

import logging
from collections.abc import Generator
from unittest import mock
from unittest.mock import patch

import pytest

from photobooth.container import Container, container
from photobooth.services.information import InformationService

logger = logging.getLogger(name=None)


@pytest.fixture(scope="module")
def _container() -> Generator[Container, None, None]:

    container.reload()
    container.stop()
    yield container
    container.start()


def test_container_reload(_container: Container):
    """container reloading works reliable"""
    container.start()

    container.reload()

    container.stop()


def test_service_start_exceptions(_container: Container):
    """container start services do not re-raise exceptions again if during start/stop to avoid breaking the whole program"""
    error_mock = mock.MagicMock()
    error_mock.side_effect = Exception("mock error")

    with patch.object(InformationService, "start", error_mock):
        try:
            container.start()
            container.stop()
        except Exception as exc:
            raise AssertionError(f"'information_service' raised an exception, but it should fail in silence {exc}") from exc


def test_service_stop_exceptions(_container: Container):
    """container start services do not re-raise exceptions again if during start/stop to avoid breaking the whole program"""
    error_mock = mock.MagicMock()
    error_mock.side_effect = Exception("mock error")

    with patch.object(InformationService, "stop", error_mock):
        try:
            container.start()
            container.stop()
        except Exception as exc:
            raise AssertionError(f"'information_service' raised an exception, but it should fail in silence {exc}") from exc
