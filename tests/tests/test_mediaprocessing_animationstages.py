"""
Testing Mediaprocessing collage
"""
import logging

import pytest
from PIL import Image

import photobooth.services.mediaprocessing.animation_pipelinestages as animation_stages
from photobooth.services.config import appconfig


@pytest.fixture(autouse=True)
def run_around_tests():
    appconfig.reset_defaults()

    yield


logger = logging.getLogger(name=None)


def test_align_sizes_stage():
    canvas_size = (400, 400)  # w, h
    captured_images = [
        Image.open("tests/assets/input.jpg"),
        Image.open("tests/assets/input.jpg"),
        Image.open("tests/assets/input.jpg"),
    ]

    stage_output = animation_stages.align_sizes_stage(canvas_size, captured_images)

    # ensure input was bigger width/height
    for input in captured_images:
        assert input.width > canvas_size[0]
        assert input.height > canvas_size[1]

    assert len(captured_images) == len(stage_output)
    for output in stage_output:
        assert output.width <= canvas_size[0]
        assert output.height <= canvas_size[1]
