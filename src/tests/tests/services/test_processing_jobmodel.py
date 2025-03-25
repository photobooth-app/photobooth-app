import logging
import time

from photobooth.container import container
from photobooth.services.config.groups.actions import SingleImageConfigurationSet, SingleImageJobControl, SingleImageProcessing, Trigger
from photobooth.services.processor.image import JobModelImage
from photobooth.utils.countdowntimer import CountdownTimer

logger = logging.getLogger(name=None)


def test_countdowntimer_zero():
    """test that 0 countdown doesn't block whole application"""

    DURATION = 0

    ct = CountdownTimer()

    ct.start(DURATION)

    start_time = time.time()
    ct.wait_countdown_finished()
    end_time = time.time()

    delta = (end_time - start_time) - DURATION

    assert abs(delta) < 0.2  # 0.2 is acceptable tolerance for any inaccuracies


def test_countdowntimer_accuracy():
    """check that timer is accurate enough"""

    DURATION = 3

    ct = CountdownTimer()

    ct.start(DURATION)

    start_time = time.time()
    ct.wait_countdown_finished()
    end_time = time.time()

    delta = (end_time - start_time) - DURATION

    assert abs(delta) < (0.1)  # 0.1 is acceptable tolerance for any inaccuracies


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

    start_time = time.time()
    jm.wait_countdown_finished()
    end_time = time.time()

    actual_blocking_time = (end_time - start_time) - expected_blocking_time

    assert abs(actual_blocking_time) < (0.1)  # 0.1 is acceptable tolerance for any inaccuracies


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
