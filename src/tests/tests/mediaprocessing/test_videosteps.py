"""
Testing Mediaprocessing collage
"""

import logging
import shutil
from pathlib import Path

import pytest

from photobooth.services.mediaprocessing.context import VideoContext
from photobooth.services.mediaprocessing.pipeline import Pipeline
from photobooth.services.mediaprocessing.steps.video import BoomerangStep, BoomerangStepPyav

from ..util import video_duration

logger = logging.getLogger(name=None)


def test_video_boomerang_stage():
    video_in = Path("src/tests/assets/video.mp4")

    context = VideoContext(video_in)
    steps = [BoomerangStep(1)]
    pipeline = Pipeline[VideoContext](*steps)
    pipeline(context)
    assert context.video_processed
    video_out = context.video_processed
    # shutil.copy(video_out, "./boomerangstep.mp4")

    # boomerang reverses video so double length
    in_dur = video_duration(video_in)
    out_dur = video_duration(video_out)

    assert out_dur == pytest.approx(in_dur * 2.0, abs=0.5)


def test_video_boomerangPyav_stage():
    video_in = Path("src/tests/assets/video.mp4")
    boomerang_speed = 3

    context = VideoContext(video_in)
    steps = [BoomerangStepPyav(boomerang_speed)]
    pipeline = Pipeline[VideoContext](*steps)
    pipeline(context)
    assert context.video_processed
    video_out = context.video_processed

    shutil.copy(video_out, "./boomerangsteppyav.mp4")

    # boomerang reverses video so double length
    in_dur = video_duration(video_in)
    out_dur = video_duration(video_out)

    assert out_dur == pytest.approx(in_dur * 2.0 * (1.0 / boomerang_speed), abs=0.5)
