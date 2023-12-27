import logging

import pytest

from photobooth.containers import ApplicationContainer
from photobooth.services.config import appconfig
from photobooth.services.containers import ServicesContainer


@pytest.fixture(autouse=True)
def run_around_tests():
    appconfig.reset_defaults()

    yield


logger = logging.getLogger(name=None)


# need fixture on module scope
@pytest.fixture(scope="module")
def services() -> ServicesContainer:
    # setup
    application_container = ApplicationContainer()

    # application_container.services().init_resources()

    # deliver
    yield application_container.services()
    application_container.services().shutdown_resources()


def proc_shoot(services: ServicesContainer):
    services.processing_service().start_job_1pic()
    # services.processing_service()._reset()


def proc_postprocess(services: ServicesContainer):
    services.processing_service()._postprocess()
    # services.processing_service()._reset()


# needs pip install pytest-benchmark
@pytest.mark.benchmark()
def test_shoot(benchmark, services):
    benchmark(proc_shoot, services)
    assert True


# needs pip install pytest-benchmark
@pytest.mark.benchmark()
def test_postprocess(benchmark, services):
    pass
    # TODO.
