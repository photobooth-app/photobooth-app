import logging
from pathlib import Path

import pytest

from photobooth.services.mediaprocessing.context import VideoContext
from photobooth.services.mediaprocessing.pipeline import Pipeline
from photobooth.services.mediaprocessing.steps.video import BoomerangStep, BoomerangStepFormerFfmpeg, LoopStep

logger = logging.getLogger(name=None)


def video_boomerangFfmpeg_stage():
    video_in = Path("src/tests/assets/video.mp4")

    context = VideoContext(video_in)
    steps = [BoomerangStepFormerFfmpeg(1)]
    pipeline = Pipeline[VideoContext](*steps)
    pipeline(context)
    assert context.video_processed


def video_boomerangPyav_stage():
    video_in = Path("src/tests/assets/video.mp4")

    context = VideoContext(video_in)
    steps = [BoomerangStep(1)]
    pipeline = Pipeline[VideoContext](*steps)
    pipeline(context)
    assert context.video_processed


def video_loopPyav_stage():
    video_in = Path("src/tests/assets/video.mp4")
    loops = 3  # will add 2 loops, so total 3 loops in resulting video

    context = VideoContext(video_in)
    steps = [LoopStep(loops)]
    pipeline = Pipeline[VideoContext](*steps)
    pipeline(context)
    assert context.video_processed


@pytest.mark.benchmark(group="create_boomerang")
def test_encode_boomerang_ffmpeg(benchmark):
    benchmark(video_boomerangFfmpeg_stage)


@pytest.mark.benchmark(group="create_boomerang")
def test_encode_boomerang_pyav(benchmark):
    benchmark(video_boomerangPyav_stage)


@pytest.mark.benchmark(group="create_boomerang")
def test_loop_pyav(benchmark):
    benchmark(video_loopPyav_stage)
