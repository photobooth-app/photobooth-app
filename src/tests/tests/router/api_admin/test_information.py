import logging
from unittest import mock
from unittest.mock import patch

from fastapi.testclient import TestClient

from photobooth.services.information import InformationService
from photobooth.services.sse.sse_ import SseEventIntervalInformationRecord, SseEventOnetimeInformationRecord

logger = logging.getLogger(name=None)


def test_get_stats_reset(client_authenticated: TestClient):
    response = client_authenticated.get("/admin/information/cntr/reset/")
    assert response.status_code == 204


def test_get_limits_reset(client_authenticated: TestClient):
    response = client_authenticated.get("/admin/information/cntr/reset/image")
    assert response.status_code == 204


def test_get_limits_reset_error(client_authenticated: TestClient):
    error_mock = mock.MagicMock()
    error_mock.side_effect = Exception()

    with patch.object(InformationService, "stats_counter_reset", error_mock):
        response = client_authenticated.get("/admin/information/cntr/reset/mockexctest")
        assert response.status_code == 500


def test_get_stats_reset_all_error(client_authenticated: TestClient):
    error_mock = mock.MagicMock()
    error_mock.side_effect = Exception()

    with patch.object(InformationService, "stats_counter_reset_all", error_mock):
        response = client_authenticated.get("/admin/information/cntr/reset/")
        assert response.status_code == 500


def test_get_stats_onetime(client_authenticated: TestClient):
    response = client_authenticated.get("/admin/information/stts/onetime")
    assert response.is_success
    assert SseEventOnetimeInformationRecord(**response.json())


def test_get_stats_interval(client_authenticated: TestClient):
    response = client_authenticated.get("/admin/information/stts/interval")
    assert response.is_success
    assert SseEventIntervalInformationRecord(**response.json())
