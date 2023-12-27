import logging
import time

from photobooth.services.config import AppConfig, appconfig
from photobooth.services.processing.jobmodels import CountdownTimer, JobModel

appconfig.__dict__.update(AppConfig())
logger = logging.getLogger(name=None)


def test_countdowntimer_zero():
    """test that 0 countdown doesn't block whole application"""

    DURATION = 0

    ct = CountdownTimer()

    ct.start(DURATION)

    start_time = time.time()
    ct.wait_countdown_finished(timeout=1)
    end_time = time.time()

    delta = (end_time - start_time) - DURATION

    assert abs(delta) < 0.2  # 0.2 is acceptable tolerance for any inaccuracies


def test_countdowntimer_accuracy():
    """check that timer is accurate enough"""

    DURATION = 3

    ct = CountdownTimer()

    ct.start(DURATION)

    start_time = time.time()
    ct.wait_countdown_finished(timeout=4)
    end_time = time.time()

    delta = (end_time - start_time) - DURATION

    assert abs(delta) < (0.1)  # 0.1 is acceptable tolerance for any inaccuracies


def test_jobmodel_start_count():
    jm = JobModel()

    expected_blocking_time = 0.75

    jm.start_countdown(1, 0.25)

    start_time = time.time()
    jm.wait_countdown_finished()
    end_time = time.time()

    actual_blocking_time = (end_time - start_time) - expected_blocking_time

    assert abs(actual_blocking_time) < (0.1)  # 0.1 is acceptable tolerance for any inaccuracies


def test_jobmodel_start_count_zero():
    jm = JobModel()

    expected_blocking_time = 0

    jm.start_countdown(0, 0)

    start_time = time.time()
    jm.wait_countdown_finished()
    end_time = time.time()

    actual_blocking_time = (end_time - start_time) - expected_blocking_time

    assert abs(actual_blocking_time) < (0.1)  # 0.1 is acceptable tolerance for any inaccuracies


def test_jobmodel_start_count_equal():
    jm = JobModel()

    expected_blocking_time = 0

    jm.start_countdown(1, 1)

    start_time = time.time()
    jm.wait_countdown_finished()
    end_time = time.time()

    actual_blocking_time = (end_time - start_time) - expected_blocking_time

    assert abs(actual_blocking_time) < (0.1)  # 0.1 is acceptable tolerance for any inaccuracies


def test_jobmodel_start_count_bigger_offset():
    jm = JobModel()

    expected_blocking_time = 0

    jm.start_countdown(1, 2)

    start_time = time.time()
    jm.wait_countdown_finished()
    end_time = time.time()

    actual_blocking_time = (end_time - start_time) - expected_blocking_time

    assert abs(actual_blocking_time) < (0.1)  # 0.1 is acceptable tolerance for any inaccuracies
