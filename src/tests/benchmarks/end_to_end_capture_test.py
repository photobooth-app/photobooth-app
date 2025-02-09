import logging
from collections.abc import Generator
from typing import cast

import pytest

from photobooth.container import Container, container
from photobooth.database.types import DimensionTypes
from photobooth.routers.media import api_getitems
from photobooth.services.backends.virtualcamera import VirtualCameraBackend
from photobooth.services.jobmodels.base import action_type_literal

logger = logging.getLogger(name=None)


@pytest.fixture(scope="module")
def _container() -> Generator[Container, None, None]:
    container.start()
    container.aquisition_service._get_stills_backend().block_until_device_is_running()
    cast(VirtualCameraBackend, container.aquisition_service._get_stills_backend())._config.emulate_hires_static_still = True

    yield container
    container.stop()


def do_end_to_end(_container: Container, action: action_type_literal):
    # 1: capture an image
    _container.processing_service.trigger_action(action, 0)
    _container.processing_service.wait_until_job_finished()

    # -: get latest item. needed for test only, but should have only little effect on benchmark
    item = _container.mediacollection_service.get_item_latest()

    # 2: emulate preview generation that can be downloaded by the client then
    api_getitems(item.id, DimensionTypes.preview)

    # job done.


@pytest.mark.benchmark(group="end_to_end_actions")
def test_end_to_end_image(benchmark, _container: Container):
    benchmark(do_end_to_end, _container, "image")


@pytest.mark.benchmark(group="end_to_end_actions")
def test_end_to_end_collage(benchmark, _container: Container):
    benchmark(do_end_to_end, _container, "collage")


# @pytest.mark.benchmark(group="end_to_end_actions")
# def test_end_to_end_video(benchmark, _container: Container):
#     # TODO: video recording would need to be subtracted from results. ...
#     benchmark(do_end_to_end, _container, "video")


@pytest.mark.benchmark(group="end_to_end_actions")
def test_end_to_end_animation(benchmark, _container: Container):
    benchmark(do_end_to_end, _container, "animation")


@pytest.mark.benchmark(group="end_to_end_actions")
def test_end_to_end_multicamera(benchmark, _container: Container):
    benchmark(do_end_to_end, _container, "multicamera")
