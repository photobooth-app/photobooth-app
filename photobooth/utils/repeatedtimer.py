"""
Repeat Timer in separate thread for tasks to be executed in intervals
"""
from threading import Timer


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
