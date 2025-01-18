import logging

import pytest
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from photobooth.container import Container, container
from photobooth.database.database import engine
from photobooth.database.models import Mediaitem
from photobooth.database.types import DimensionTypes
from photobooth.routers.media import api_getitems

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

    # get last element by last_insert_rowid instead collections getlastitem because datetime resolution is only 1 sec
    with Session(engine) as session:
        res = session.scalar(text("SELECT last_insert_rowid() FROM mediaitems"))
        last_id = session.scalars(select(Mediaitem.id).where(text(f"rowid=={res}"))).one()

    api_getitems(last_id, DimensionTypes.preview)


@pytest.mark.benchmark()
def test_wait_for_still(benchmark, _container: Container):
    benchmark(wait_for_still, _container)


@pytest.mark.benchmark()
def test_end_to_end_still(benchmark, _container: Container):
    benchmark(end_to_end_still, _container)
