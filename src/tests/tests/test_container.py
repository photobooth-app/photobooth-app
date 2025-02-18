"""
Testing exceptions in backends
"""

import logging
from unittest import mock
from unittest.mock import patch

from photobooth.container import container
from photobooth.services.information import InformationService

logger = logging.getLogger(name=None)


def test_container_reload():
    """container reloading works reliable"""

    for _ in range(1, 5):
        container.reload()


def test_service_start_exceptions():
    """container start services do not re-raise exceptions again if during start/stop to avoid breaking the whole program"""
    error_mock = mock.MagicMock()
    error_mock.side_effect = Exception("mock error")

    with patch.object(InformationService, "start", error_mock):
        try:
            container.start()
            container.stop()
        except Exception as exc:
            raise AssertionError(f"'information_service' raised an exception, but it should fail in silence {exc}") from exc


def test_service_stop_exceptions():
    """container start services do not re-raise exceptions again if during start/stop to avoid breaking the whole program"""
    error_mock = mock.MagicMock()
    error_mock.side_effect = Exception("mock error")

    with patch.object(InformationService, "stop", error_mock):
        try:
            container.start()
            container.stop()
        except Exception as exc:
            raise AssertionError(f"'information_service' raised an exception, but it should fail in silence {exc}") from exc
