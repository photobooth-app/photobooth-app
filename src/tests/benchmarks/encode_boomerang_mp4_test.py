import logging
from pathlib import Path

import pytest

from photobooth.services.mediaprocessing.context import VideoContext
from photobooth.services.mediaprocessing.pipeline import Pipeline
from photobooth.services.mediaprocessing.steps.video import BoomerangStep, BoomerangStepPyav

logger = logging.getLogger(name=None)


def video_boomerang_stage():
    video_in = Path("src/tests/assets/video.mp4")

    context = VideoContext(video_in)
    steps = [BoomerangStep(1)]
    pipeline = Pipeline[VideoContext](*steps)
    pipeline(context)
    assert context.video_processed


def video_boomerangPyav_stage():
    video_in = Path("src/tests/assets/video.mp4")

    context = VideoContext(video_in)
    steps = [BoomerangStepPyav(1)]
    pipeline = Pipeline[VideoContext](*steps)
    pipeline(context)
    assert context.video_processed


@pytest.mark.benchmark(group="create_boomerang")
def test_encode_boomerang_ffmpeg(benchmark):
    benchmark(video_boomerang_stage)


@pytest.mark.benchmark(group="create_boomerang")
def test_encode_boomerang_pyav(benchmark):
    benchmark(video_boomerangPyav_stage)
