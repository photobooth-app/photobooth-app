import logging
import time

import pytest

from photobooth.utils.countdowntimer import CountdownTimer

logger = logging.getLogger(name=None)


def test_countdowntimer_zero():
    """test that 0 countdown doesn't block whole application"""

    DURATION = 0

    ct = CountdownTimer()

    ct.start(DURATION)

    start_time = time.perf_counter()
    ct.wait_countdown_finished()
    end_time = time.perf_counter()

    actual = end_time - start_time
    assert pytest.approx(DURATION, abs=0.1) == actual  # 0.1 is acceptable tolerance for any inaccuracies


def test_countdowntimer_accuracy():
    """check that timer is accurate enough"""

    DURATION = 1

    ct = CountdownTimer()

    ct.start(DURATION)

    start_time = time.perf_counter()
    ct.wait_countdown_finished()
    end_time = time.perf_counter()

    actual = end_time - start_time
    assert pytest.approx(DURATION, abs=0.1) == actual  # 0.1 is acceptable tolerance for any inaccuracies
