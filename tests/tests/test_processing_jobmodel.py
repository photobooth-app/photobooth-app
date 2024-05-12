import logging
import time

import pytest

from photobooth.services.config import appconfig
from photobooth.services.processing.jobmodels import CountdownTimer, JobModelImage, SingleImageProcessing


@pytest.fixture(autouse=True)
def run_around_tests():
    appconfig.reset_defaults()

    yield


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
    jm = JobModelImage(SingleImageProcessing())

    expected_blocking_time = 0.75

    jm.start_countdown(1, 0.25)

    start_time = time.time()
    jm.wait_countdown_finished()
    end_time = time.time()

    actual_blocking_time = (end_time - start_time) - expected_blocking_time

    assert abs(actual_blocking_time) < (0.1)  # 0.1 is acceptable tolerance for any inaccuracies


def test_jobmodel_start_count_zero():
    jm = JobModelImage(SingleImageProcessing())

    expected_blocking_time = 0

    jm.start_countdown(0, 0)

    start_time = time.time()
    jm.wait_countdown_finished()
    end_time = time.time()

    actual_blocking_time = (end_time - start_time) - expected_blocking_time

    assert abs(actual_blocking_time) < (0.1)  # 0.1 is acceptable tolerance for any inaccuracies


def test_jobmodel_start_count_equal():
    jm = JobModelImage(SingleImageProcessing())

    expected_blocking_time = 0

    jm.start_countdown(1, 1)

    start_time = time.time()
    jm.wait_countdown_finished()
    end_time = time.time()

    actual_blocking_time = (end_time - start_time) - expected_blocking_time

    assert abs(actual_blocking_time) < (0.1)  # 0.1 is acceptable tolerance for any inaccuracies


def test_jobmodel_start_count_bigger_offset():
    jm = JobModelImage(SingleImageProcessing())

    expected_blocking_time = 0

    jm.start_countdown(1, 2)

    start_time = time.time()
    jm.wait_countdown_finished()
    end_time = time.time()

    actual_blocking_time = (end_time - start_time) - expected_blocking_time

    assert abs(actual_blocking_time) < (0.1)  # 0.1 is acceptable tolerance for any inaccuracies
