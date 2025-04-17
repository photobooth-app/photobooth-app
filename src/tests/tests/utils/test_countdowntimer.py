import logging
import time

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
