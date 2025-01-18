import logging

import pytest

from photobooth.container import Container, container

logger = logging.getLogger(name=None)


@pytest.fixture(scope="module")
def _container() -> Container:
    container.start()
    container.aquisition_service._main_backend.block_until_device_is_running()

    yield container
    container.stop()


def do_end_to_end(_container: Container, action: str):
    # 1: capture an image
    _container.processing_service.trigger_action(action, 0)
    _container.processing_service.wait_until_job_finished()

    # -: get latest item. needed for test only, but should have only little effect on benchmark
    # item = _container.mediacollection_service.db_get_most_recent_mediaitem()

    # 2: emulate preview generation that can be downloaded by the client then
    pass  # in v4 the thumbs are all generated right after processing. so we do not need to take this into account here it's included above.

    # job done.


@pytest.mark.benchmark(group="end_to_end_actions")
def test_end_to_end_image(benchmark, _container: Container):
    benchmark(do_end_to_end, _container, "image")


@pytest.mark.benchmark(group="end_to_end_actions")
def test_end_to_end_collage(benchmark, _container: Container):
    benchmark(do_end_to_end, _container, "collage")


@pytest.mark.benchmark(group="end_to_end_actions")
def test_end_to_end_video(benchmark, _container: Container):
    # TODO: video recording would need to be subtracted from results. ...
    benchmark(do_end_to_end, _container, "video")


@pytest.mark.benchmark(group="end_to_end_actions")
def test_end_to_end_animation(benchmark, _container: Container):
    benchmark(do_end_to_end, _container, "animation")
