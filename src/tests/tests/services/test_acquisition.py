import io
import logging
import time
from collections.abc import Generator
from unittest import mock
from unittest.mock import patch

import pytest
from PIL import Image

from photobooth.models.stillretry import StillRetry
from photobooth.plugins import hookimpl
from photobooth.plugins import pm as pluggy_pm
from photobooth.services.acquisition import MAX_STILL_RETRIES, AcquisitionService
from tests.tests.util import block_until_device_is_running

logger = logging.getLogger(name=None)


@pytest.fixture(scope="module")
def _acqs() -> Generator[AcquisitionService, None, None]:
    acqs = AcquisitionService()
    acqs.start()
    yield acqs
    acqs.stop()


def test_getimage(_acqs: AcquisitionService):
    with Image.open(_acqs.wait_for_still_file()) as img:
        logger.info(img)
        img.verify()


def test_getimages_directlyaccess_backends(_acqs: AcquisitionService):
    with Image.open(_acqs._backends[0].wait_for_still_file()) as img:
        logger.info(img)
        img.verify()

    with Image.open(io.BytesIO(_acqs._backends[0].wait_for_lores_image())) as img:
        logger.info(img)
        img.verify()


def test_get_multicam_files(_acqs: AcquisitionService):
    for image in _acqs.wait_for_multicam_files():
        with Image.open(image) as img:
            logger.info(img)
            img.verify()


def test_getvideo(_acqs: AcquisitionService):
    """get video from service"""
    videopath = _acqs.start_recording()
    time.sleep(2)
    _acqs.stop_recording()

    logger.info(f"video stored to file {videopath}")
    assert videopath and videopath.is_file()


def test_simulated_init_exceptions(_acqs: AcquisitionService):
    # test to ensure a failing backend doesnt break the whole system due to uncatched exceptions
    from photobooth.services.backends.virtualcamera import VirtualCameraBackend

    error_mock = mock.MagicMock()
    error_mock.side_effect = Exception("mock error")

    with patch.object(VirtualCameraBackend, "__init__", error_mock):
        try:
            _: AcquisitionService = AcquisitionService()
        except Exception as exc:
            raise AssertionError(f"'VirtualCameraBackend' raised an exception, but it should fail in silence {exc}") from exc


def test_simulated_setup_device_exceptions(_acqs: AcquisitionService):
    # test to ensure a failing backend doesnt break the whole system due to uncatched exceptions
    from photobooth.services.backends.virtualcamera import VirtualCameraBackend

    error_mock = mock.MagicMock()
    error_mock.side_effect = Exception("mock error")

    with patch.object(VirtualCameraBackend, "setup_resource", error_mock):
        try:
            aq: AcquisitionService = AcquisitionService()
            aq.start()

        except Exception as exc:
            raise AssertionError(f"'VirtualCameraBackend' raised an exception, but it should fail in silence {exc}") from exc

        # stop to ensure the threads are stopped if there are any.
        aq.stop()


def test_simulated_stop_exceptions(_acqs: AcquisitionService):
    # test to ensure a failing backend doesnt break the whole system due to uncatched exceptions
    from photobooth.services.backends.virtualcamera import VirtualCameraBackend

    error_mock = mock.MagicMock()
    error_mock.side_effect = Exception("mock error")

    with patch.object(VirtualCameraBackend, "stop", error_mock):
        try:
            aq: AcquisitionService = AcquisitionService()
            aq.stop()

        except Exception as exc:
            raise AssertionError(f"'VirtualCameraBackend' raised an exception, but it should fail in silence {exc}") from exc


def test_get_livestream_virtualcamera(_acqs: AcquisitionService):
    block_until_device_is_running(_acqs._video_backend)

    i = 0
    for i in range(10):  # frame is bytes
        frame = _acqs.wait_for_lores_image()
        i = i + 1

        # ensure we always receive a valid jpeg frame, nothing else.
        # in case the backend failed, we receive a substitute image
        assert frame.startswith(b"\xff\xd8\xff")

        if i == 5:
            # trigger virtual camera to send fault flag - this should result in supervisor stopping device, restart and continue deliver
            _acqs._video_backend.recover()

    assert i == 10


class _RetryPlugin:
    def __init__(self, retries: int):
        self.retries = retries
        self.seen_attempts: list[int] = []

    @hookimpl
    def acq_still_check(self, file, retry_attempt):
        self.seen_attempts.append(retry_attempt)
        if retry_attempt < self.retries:
            return StillRetry(parameters={"iso": "100"}, reason="test")
        return None


def _run_with_plugin(_acqs: AcquisitionService, plugin: _RetryPlugin):
    backend = _acqs._stills_backend
    overrides_during_capture: list[dict] = []
    original = backend.wait_for_still_file

    def spy(*args, **kwargs):
        overrides_during_capture.append(dict(backend.still_parameter_overrides))
        return original(*args, **kwargs)

    pluggy_pm.register(plugin)
    try:
        with patch.object(backend, "wait_for_still_file", side_effect=spy):
            _acqs.wait_for_still_file()
    finally:
        pluggy_pm.unregister(plugin)

    return backend, overrides_during_capture


def test_still_check_hook_retry_uses_temporary_overrides(_acqs: AcquisitionService):
    plugin = _RetryPlugin(retries=1)
    backend, overrides_during_capture = _run_with_plugin(_acqs, plugin)

    assert plugin.seen_attempts == [0, 1]  # original capture and the photo of the retry
    assert overrides_during_capture == [{}, {"iso": "100"}]  # retry parameters apply to the retry only
    assert backend.still_parameter_overrides == {}  # and are removed afterwards


def test_still_check_hook_retries_are_limited(_acqs: AcquisitionService):
    plugin = _RetryPlugin(retries=99)
    _, overrides_during_capture = _run_with_plugin(_acqs, plugin)

    assert len(overrides_during_capture) == 1 + MAX_STILL_RETRIES
