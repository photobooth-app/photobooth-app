import logging
import time
from collections.abc import Generator
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

from photobooth.services.acquisition import AcquisitionService
from photobooth.services.config.groups.actions import SingleImageConfigurationSet, SingleImageJobControl, SingleImageProcessing, Trigger
from photobooth.services.processor.image import JobModelImage

logger = logging.getLogger(name=None)


@pytest.fixture(scope="module")
def _acqs() -> Generator[AcquisitionService, None, None]:
    acqs = AcquisitionService()
    acqs.start()
    yield acqs
    acqs.stop()


def test_jobmodel_start_count(_acqs: AcquisitionService):
    countdown_time = 1
    offset = 0.25
    expected_blocking_time = countdown_time - offset

    jm = JobModelImage(
        SingleImageConfigurationSet(
            jobcontrol=SingleImageJobControl(countdown_capture=countdown_time),
            processing=SingleImageProcessing(),
            trigger=Trigger(),
        ),
        _acqs,
    )

    jm.start_countdown(offset)

    start_time = time.perf_counter()
    jm.wait_countdown_finished()
    end_time = time.perf_counter()

    actual_blocking_time = end_time - start_time

    assert pytest.approx(expected_blocking_time, abs=0.2) == actual_blocking_time  # 0.2 is acceptable tolerance for any inaccuracies


def test_jobmodel_start_count_zero(_acqs: AcquisitionService):
    countdown_time = 0
    offset = 0
    expected_blocking_time = countdown_time - offset

    jm = JobModelImage(
        SingleImageConfigurationSet(
            jobcontrol=SingleImageJobControl(countdown_capture=countdown_time),
            processing=SingleImageProcessing(),
            trigger=Trigger(),
        ),
        _acqs,
    )

    jm.start_countdown(offset)

    start_time = time.time()
    jm.wait_countdown_finished()
    end_time = time.time()

    actual_blocking_time = (end_time - start_time) - expected_blocking_time

    assert abs(actual_blocking_time) < (0.1)  # 0.1 is acceptable tolerance for any inaccuracies


def test_jobmodel_start_count_equal(_acqs: AcquisitionService):
    countdown_time = 1
    offset = 1
    expected_blocking_time = countdown_time - offset

    jm = JobModelImage(
        SingleImageConfigurationSet(
            jobcontrol=SingleImageJobControl(countdown_capture=countdown_time),
            processing=SingleImageProcessing(),
            trigger=Trigger(),
        ),
        _acqs,
    )

    jm.start_countdown(offset)

    start_time = time.time()
    jm.wait_countdown_finished()
    end_time = time.time()

    actual_blocking_time = (end_time - start_time) - expected_blocking_time

    assert abs(actual_blocking_time) < (0.1)  # 0.1 is acceptable tolerance for any inaccuracies


def test_jobmodel_start_count_bigger_offset(_acqs: AcquisitionService):
    countdown_time = 1
    offset = 2
    expected_blocking_time = 0  # in this case due to camera delay longer than actual countdown, the blocking time is skipped.

    jm = JobModelImage(
        SingleImageConfigurationSet(
            jobcontrol=SingleImageJobControl(countdown_capture=countdown_time),
            processing=SingleImageProcessing(),
            trigger=Trigger(),
        ),
        _acqs,
    )

    jm.start_countdown(offset)

    start_time = time.time()
    jm.wait_countdown_finished()
    end_time = time.time()

    actual_blocking_time = (end_time - start_time) - expected_blocking_time

    assert abs(actual_blocking_time) < (0.1)  # 0.1 is acceptable tolerance for any inaccuracies


def test_jobmodel_frame_overlay_preview(_acqs: AcquisitionService):
    jm = JobModelImage(
        SingleImageConfigurationSet(
            jobcontrol=SingleImageJobControl(),
            processing=SingleImageProcessing(
                img_frame_enable=True,
                img_frame_file=Path("userdata/demoassets/frames/frame_image_photobooth-app.png"),
                img_frame_preview_mirror=True,
            ),
            trigger=Trigger(),
        ),
        _acqs,
    )

    assert jm.frame_overlay is not None
    assert jm.frame_overlay.mirror_effect is True


def test_jobmodel_frame_overlay_preview_disabled(_acqs: AcquisitionService):
    jm = JobModelImage(
        SingleImageConfigurationSet(
            jobcontrol=SingleImageJobControl(),
            processing=SingleImageProcessing(
                img_frame_enable=True,
                img_frame_file=Path("userdata/demoassets/frames/frame_image_photobooth-app.png"),
                img_frame_preview_enable=False,
            ),
            trigger=Trigger(),
        ),
        _acqs,
    )

    assert jm.frame_overlay is None
    assert jm.captures_definition  # livestream is cropped to the transparent area instead


def test_jobmodel_frame_preview_disabled_crops_to_transparent_area(_acqs: AcquisitionService, tmp_path: Path):
    frame_file = tmp_path / "frame.png"
    img = Image.new("RGBA", (1000, 800), (255, 0, 0, 255))
    ImageDraw.Draw(img).rectangle((100, 50, 899, 449), fill=(0, 0, 0, 0))  # transparent area 800x400
    img.save(frame_file)

    jm = JobModelImage(
        SingleImageConfigurationSet(
            jobcontrol=SingleImageJobControl(),
            processing=SingleImageProcessing(img_frame_enable=True, img_frame_file=frame_file, img_frame_preview_enable=False),
            trigger=Trigger(),
        ),
        _acqs,
    )

    assert jm.captures_definition
    assert (jm.captures_definition.width, jm.captures_definition.height) == (800, 400)
