import logging

import pytest

from photobooth.container import Container, container
from photobooth.services.config import appconfig

logger = logging.getLogger(name=None)


@pytest.fixture(scope="module")
def _container() -> Container:
    container.start()
    container.aquisition_service._get_stills_backend().block_until_device_is_running()

    yield container
    container.stop()


def wait_for_still(_container: Container):
    # this test is probably just measuring how fast the backend delivers, not the processing itself.
    _container.aquisition_service.wait_for_still_file()


def end_to_end_still(_container: Container):
    container.processing_service.trigger_action("image", 0)
    _container.processing_service.wait_until_job_finished()


@pytest.mark.benchmark()
def test_end_to_end_image(benchmark, _container: Container):
    benchmark(wait_for_still, _container)


@pytest.mark.benchmark()
def test_end_to_end_still(benchmark, _container: Container):
    appconfig.actions.image[0].jobcontrol.countdown_capture = 0.0

    benchmark(end_to_end_still, _container)
