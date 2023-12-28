import logging

import pytest

from photobooth.container import Container, container
from photobooth.services.config import appconfig

logger = logging.getLogger(name=None)


@pytest.fixture(autouse=True)
def run_around_tests():
    appconfig.reset_defaults()

    yield


@pytest.fixture(scope="function")
def _container() -> Container:
    # setup

    container.start()

    # deliver
    yield container
    container.stop()


def proc_shoot(_container: Container):
    _container.processing_service.start_job_1pic()
    # _container.processing_service._reset()


# needs pip install pytest-benchmark
@pytest.mark.benchmark()
def test_shoot(benchmark, services):
    benchmark(proc_shoot, services)
    assert True
