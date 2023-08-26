import logging

import pytest
from dependency_injector import providers
from pymitter import EventEmitter

from photobooth.appconfig import AppConfig
from photobooth.services.containers import ServicesContainer

logger = logging.getLogger(name=None)


# need fixture on module scope
@pytest.fixture(scope="module")
def services() -> ServicesContainer:
    # setup
    evtbus = providers.Singleton(EventEmitter)
    config = providers.Singleton(AppConfig)
    services = ServicesContainer(
        evtbus=evtbus,
        config=config,
    )

    services.init_resources()

    # deliver
    yield services
    services.shutdown_resources()


def proc_shoot(services: ServicesContainer):
    services.processing_service().shoot()
    services.processing_service()._reset()


def proc_postprocess(services: ServicesContainer):
    services.processing_service().postprocess()
    services.processing_service()._reset()


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
