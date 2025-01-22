import threading

# use like this is preferred:
#
# class MyTask(StoppableThread):
#     def run(self):
#         while not self.stopped():
#             time.sleep(1)
#             print("Hello")
#
# testthread = MyTask()
# testthread.start()
# time.sleep(5)
# testthread.stop()
#
# otherwise:
#
# def funct():
#     while not current_thread().stopped():
#         time.sleep(1)
#         print("Hello")


# testthread = StoppableThread(target=funct)
# testthread.start()
# sleep(5)
# testthread.stop()


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
