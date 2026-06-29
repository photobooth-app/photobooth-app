import logging
import os
from pathlib import Path

import psutil
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


def measure_rss_with_children(func):
    proc = psutil.Process(os.getpid())
    before = proc.memory_info().rss
    before_children = sum(p.memory_info().rss for p in proc.children(recursive=True))

    func()

    after = proc.memory_info().rss
    after_children = sum(p.memory_info().rss for p in proc.children(recursive=True))

    return (after + after_children) - (before + before_children)


def test_memory_boomerang_ffmpeg():
    delta = measure_rss_with_children(video_boomerang_stage)
    logger.info(f"FFmpeg RSS delta: {delta / 1024 / 1024}")


def test_memory_boomerang_pyav():
    delta = measure_rss_with_children(video_boomerangPyav_stage)
    logger.info(f"PyAV RSS delta: {delta / 1024 / 1024}")
