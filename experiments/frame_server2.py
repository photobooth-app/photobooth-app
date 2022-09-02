#!/usr/bin/python3

# These two are only needed for the demo code below the FrameServer class.
from picamera2 import Picamera2
import time

from threading import Condition, Thread


class FrameServer:
    def __init__(self, picam2):
        """A simple class that can serve up frames from one of the Picamera2's configured
        streams to multiple other threads.
        Pass in the Picamera2 object and the name of the stream for which you want
        to serve up frames."""
        self._picam2 = picam2
        self._hq_array = None
        self._lores_array = None
        self._hq_condition = Condition()
        self._lores_condition = Condition()
        self._trigger_hq_capture = False
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
        self._thread.join(1)

    def trigger_hq_capture(self):
        """switch one time to hq capture"""
        self._trigger_hq_capture = True

    def _thread_func(self):
        while self._running:
            if not self._trigger_hq_capture:
                array = self._picam2.capture_array("lores")
                with self._lores_condition:
                    self._lores_array = array
                    self._lores_condition.notify_all()
            else:
                # only capture one pic and return to lores streaming afterwards
                self._trigger_hq_capture = False

                # capture hq picture
                array = self._picam2.capture_array("main")
                with self._hq_condition:
                    self._hq_array = array
                    self._hq_condition.notify_all()

            self._count += 1

    def wait_for_lores_frame(self):
        """for other threads to receive a lores frame"""
        with self._lores_condition:
            while True:
                self._lores_condition.wait()
                return self._lores_array

    def wait_for_hq_frame(self):
        """for other threads to receive a hq frame"""
        with self._hq_condition:
            while True:
                self._hq_condition.wait()
                return self._hq_array

# Below here is just demo code that uses the class:


def thread1_func():
    global thread1_count
    while not thread_abort:
        frame = frameServer.wait_for_hq_frame()
        thread1_count += 1


def thread2_func():
    global thread2_count
    frame = None
    while not thread_abort:
        frame = frameServer.wait_for_lores_frame()
        thread2_count += 1


thread_abort = False
thread1_count = 0
thread2_count = 0
thread1 = Thread(target=thread1_func, daemon=True)
thread2 = Thread(target=thread2_func, daemon=True)

picam2 = Picamera2()
full_resolution = picam2.sensor_resolution
half_resolution = [dim // 2 for dim in picam2.sensor_resolution]
main_stream = {"size": full_resolution}
lores_stream = {"size": (640, 480)}
video_config = picam2.create_still_configuration(
    main_stream, lores_stream, encode="lores")
picam2.configure(video_config)
frameServer = FrameServer(picam2)
thread1.start()
thread2.start()
frameServer.start()
picam2.start()

time.sleep(5)

frameServer.trigger_hq_capture()

thread_abort = True
thread1.join(timeout=1)
thread2.join(timeout=1)
frameServer.stop()
picam2.stop()

print("Thread1 received", thread1_count, "frames")
print("Thread2 received", thread2_count, "frames")
print("serverMain received", frameServer.count, "frames")
