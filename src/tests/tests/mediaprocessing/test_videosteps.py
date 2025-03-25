"""
Testing Mediaprocessing collage
"""

import logging
from pathlib import Path

import pytest

from photobooth.services.mediaprocessing.context import VideoContext
from photobooth.services.mediaprocessing.pipeline import Pipeline
from photobooth.services.mediaprocessing.steps.video import BoomerangStep

from ..util import video_duration

logger = logging.getLogger(name=None)


def test_video_boomerang_stage():
    video_in = Path("src/tests/assets/video.mp4")

    context = VideoContext(video_in)
    steps = [BoomerangStep()]
    pipeline = Pipeline[VideoContext](*steps)
    pipeline(context)
    assert context.video_processed
    video_out = context.video_processed

    # boomerang reverses video so double length
    in_dur = video_duration(video_in)
    out_dur = video_duration(video_out)

    assert out_dur == pytest.approx(in_dur * 2.0, 0.3)
