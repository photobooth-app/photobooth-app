import logging
import time

from photobooth.services.processing.jobmodels import CountdownTimer, JobModel

logger = logging.getLogger(name=None)


def test_countdowntimer_zero():
    """test that 0 countdown doesn't block whole application"""
    ct = CountdownTimer()

    ct.start(0)

    start_time = time.time()
    ct.wait_countdown_finished(timeout=1)
    end_time = time.time()

    assert end_time - start_time < 0.2  # 0.2 is acceptable tolerance for any inaccuracies


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


def test_jobmodel_start_count_zero():
    jm = JobModel()

    jm.start_countdown(0, 0)
    jm.wait_countdown_finished()


def test_jobmodel_start_count_equal():
    jm = JobModel()

    jm.start_countdown(1, 1)
    jm.wait_countdown_finished()


def test_jobmodel_start_count_bigger_offset():
    jm = JobModel()

    jm.start_countdown(1, 2)
    jm.wait_countdown_finished()
