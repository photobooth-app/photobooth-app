import logging
import time

import pytest

from photobooth.container import container
from photobooth.services.config.groups.actions import SingleImageConfigurationSet, SingleImageJobControl, SingleImageProcessing, Trigger
from photobooth.services.processor.image import JobModelImage

logger = logging.getLogger(name=None)


def test_jobmodel_start_count():
    countdown_time = 1
    offset = 0.25
    expected_blocking_time = countdown_time - offset

    jm = JobModelImage(
        SingleImageConfigurationSet(
            jobcontrol=SingleImageJobControl(countdown_capture=countdown_time),
            processing=SingleImageProcessing(),
            trigger=Trigger(),
        ),
        container.aquisition_service,
    )

    jm.start_countdown(offset)

    start_time = time.perf_counter()
    jm.wait_countdown_finished()
    end_time = time.perf_counter()

    actual_blocking_time = end_time - start_time

    assert pytest.approx(expected_blocking_time, abs=0.2) == actual_blocking_time  # 0.2 is acceptable tolerance for any inaccuracies


def test_jobmodel_start_count_zero():
    countdown_time = 0
    offset = 0
    expected_blocking_time = countdown_time - offset

    jm = JobModelImage(
        SingleImageConfigurationSet(
            jobcontrol=SingleImageJobControl(countdown_capture=countdown_time),
            processing=SingleImageProcessing(),
            trigger=Trigger(),
        ),
        container.aquisition_service,
    )

    jm.start_countdown(offset)

    start_time = time.time()
    jm.wait_countdown_finished()
    end_time = time.time()

    actual_blocking_time = (end_time - start_time) - expected_blocking_time

    assert abs(actual_blocking_time) < (0.1)  # 0.1 is acceptable tolerance for any inaccuracies


def test_jobmodel_start_count_equal():
    countdown_time = 1
    offset = 1
    expected_blocking_time = countdown_time - offset

    jm = JobModelImage(
        SingleImageConfigurationSet(
            jobcontrol=SingleImageJobControl(countdown_capture=countdown_time),
            processing=SingleImageProcessing(),
            trigger=Trigger(),
        ),
        container.aquisition_service,
    )

    jm.start_countdown(offset)

    start_time = time.time()
    jm.wait_countdown_finished()
    end_time = time.time()

    actual_blocking_time = (end_time - start_time) - expected_blocking_time

    assert abs(actual_blocking_time) < (0.1)  # 0.1 is acceptable tolerance for any inaccuracies


def test_jobmodel_start_count_bigger_offset():
    countdown_time = 1
    offset = 2
    expected_blocking_time = 0  # in this case due to camera delay longer than actual countdown, the blocking time is skipped.

    jm = JobModelImage(
        SingleImageConfigurationSet(
            jobcontrol=SingleImageJobControl(countdown_capture=countdown_time),
            processing=SingleImageProcessing(),
            trigger=Trigger(),
        ),
        container.aquisition_service,
    )

    jm.start_countdown(offset)

    start_time = time.time()
    jm.wait_countdown_finished()
    end_time = time.time()

    actual_blocking_time = (end_time - start_time) - expected_blocking_time

    assert abs(actual_blocking_time) < (0.1)  # 0.1 is acceptable tolerance for any inaccuracies
