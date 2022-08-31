#!/usr/bin/python3

# These two are only needed for the demo code below the FrameServer class.
from picamera2 import Picamera2
import time

from threading import Condition, Thread


class FrameServer:
    def __init__(self, picam2, stream='main'):
        """A simple class that can serve up frames from one of the Picamera2's configured
        streams to multiple other threads.
        Pass in the Picamera2 object and the name of the stream for which you want
        to serve up frames."""
        self._picam2 = picam2
        self._stream = stream
        self._array = None
        self._condition = Condition()
        self._running = True
        self._count = 0
        self._thread = Thread(target=self._thread_func, daemon=True)

    @property
    def count(self):
        """A count of the number of frames received."""
        return self._count

    def start(self):
        """To start the FrameServer, you will also need to start the Picamera2 object."""
        self._thread.start()

    def stop(self):
        """To stop the FrameServer, first stop any client threads (that might be
        blocked in wait_for_frame), then call this stop method. Don't stop the
        Picamera2 object until the FrameServer has been stopped."""
        self._running = False
        self._thread.join()

    def _thread_func(self):
        while self._running:
            array = self._picam2.capture_array(self._stream)
            self._count += 1
            with self._condition:
                self._array = array
                self._condition.notify_all()

    def wait_for_frame(self, previous=None):
        """You may optionally pass in the previous frame that you got last time you
        called this function. This will guarantee that you don't get duplicate frames
        returned in the event of spurious wake-ups, and it may even return more
        quickly in the case where a new frame has already arrived."""
        with self._condition:
            if previous is not None and self._array is not previous:
                return self._array
            while True:
                self._condition.wait()
                if self._array is not previous:
                    return self._array


# Below here is just demo code that uses the class:

def thread1_func():
    global thread1_count
    while not thread_abort:
        frame = serverMain.wait_for_frame()
        thread1_count += 1


def thread2_func():
    global thread2_count
    frame = None
    while not thread_abort:
        frame = serverLores.wait_for_frame(frame)
        thread2_count += 1


thread_abort = False
thread1_count = 0
thread2_count = 0
thread1 = Thread(target=thread1_func)
thread2 = Thread(target=thread2_func)

picam2 = Picamera2()
half_resolution = [dim // 2 for dim in picam2.sensor_resolution]
main_stream = {"size": half_resolution}
lores_stream = {"size": (640, 480)}
video_config = picam2.create_still_configuration(
    main_stream, lores_stream, encode="lores")
picam2.configure(video_config)
serverMain = FrameServer(picam2)
serverLores = FrameServer(picam2, 'lores')
# thread1.start()
thread2.start()
# serverMain.start()
serverLores.start()
picam2.start()

time.sleep(5)

thread_abort = True
# thread1.join()
thread2.join()
# serverMain.stop()
serverLores.stop()
picam2.stop()

print("Thread1 received", thread1_count, "frames")
print("Thread2 received", thread2_count, "frames")
print("serverMain received", serverMain.count, "frames")
print("serverLores received", serverLores.count, "frames")
