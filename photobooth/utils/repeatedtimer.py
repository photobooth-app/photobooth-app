"""
Repeat Timer in separate thread for tasks to be executed in intervals
"""

from threading import Event, Thread

# The timer class was contributed by Itamar Shtull-Trauring
# 2023-10-30 change Thread.__init__(self) to THread.__init__(self, daemon=True)


class Timer(Thread):
    """Call a function after a specified number of seconds:

    t = Timer(30.0, f, args=None, kwargs=None)
    t.start()
    t.cancel()     # stop the timer's action if it's still waiting

    """

    def __init__(self, interval, function, args=None, kwargs=None):
        Thread.__init__(self, daemon=True)
        self.interval = interval
        self.function = function
        self.args = args if args is not None else []
        self.kwargs = kwargs if kwargs is not None else {}
        self.finished = Event()

    def cancel(self):
        """Stop the timer if it hasn't finished yet."""
        self.finished.set()

    def run(self):
        self.finished.wait(self.interval)
        if not self.finished.is_set():
            self.function(*self.args, **self.kwargs)
        self.finished.set()


class RepeatedTimer:
    """_summary_"""

    def __init__(self, interval: float, function, *args, **kwargs):
        self._timer = None
        self.interval: float = interval
        self.function = function
        self.args = args
        self.kwargs = kwargs
        self.is_running = False
        # self.start()

    def _run(self):
        """_summary_"""
        self.is_running = False
        self.start()
        self.function(*self.args, **self.kwargs)

    def start(self):
        """_summary_"""
        if not self.is_running:
            self._timer = Timer(self.interval, self._run)
            self._timer.start()
            self.is_running = True

    def stop(self):
        """_summary_"""
        if self._timer:  # if timer was never started, no cancel on nonetype
            self._timer.cancel()
        self.is_running = False
