"""_summary_
"""
import threading


class StoppableThread(threading.Thread):
    """Thread class with a stop() method. The thread itself has to check
    regularly for the stopped() condition."""

    def __init__(self, *args, **kwargs):
        """_summary_"""
        super().__init__(*args, **kwargs)
        self._stop_event = threading.Event()

    def stop(self):
        """_summary_"""
        self._stop_event.set()

    def stopped(self):
        """check in run loop. break loop if stopped() returns True

        Returns:
            _type_: _description_
        """
        return self._stop_event.is_set()
