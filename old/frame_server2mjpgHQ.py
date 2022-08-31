#!/usr/bin/python3

from PIL import Image
from picamera2 import Picamera2
import time
import cv2
import simplejpeg
from threading import Condition, Thread

DEBUG = True


class FrameServer:
    def __init__(self, picam2):
        """A simple class that can serve up frames from one of the Picamera2's configured
        streams to multiple other threads.
        Pass in the Picamera2 object and the name of the stream for which you want
        to serve up frames."""
        self._picam2 = picam2
        self._hq_array = None
        self._lores_array = None
        self._lores_convert_to_jpeg = True
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
                array = picam2.capture_array("lores")

                if self._lores_convert_to_jpeg:
                    rgb = cv2.cvtColor(array, cv2.COLOR_YUV420p2RGB)
                    buf = simplejpeg.encode_jpeg(
                        rgb, quality=80, colorspace='BGR', colorsubsampling='420')
                    size = len(buf)
                    print('mjpeg conversion active', "jpeg size: ",
                          round(size/1000, 1), "kb")

                    array = buf

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
        PIL_image = Image.fromarray(frame.astype('uint8'), 'RGB')
        PIL_image.save("frame_server2mjpgHQ.jpeg", quality=85)

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
main_stream = {"size": half_resolution}
lores_stream = {"size": (640, 480)}
config = picam2.create_still_configuration(
    main_stream, lores_stream, encode="lores", buffer_count=1, display="lores")
picam2.configure(config)
frameServer = FrameServer(picam2)
thread1.start()
thread2.start()
frameServer.start()
picam2.start(show_preview=DEBUG)

time.sleep(1)

frameServer.trigger_hq_capture()


thread_abort = True
thread1.join(timeout=1)
thread2.join(timeout=1)
frameServer.stop()
picam2.stop()

print("Thread1 received", thread1_count, "frames")
print("Thread2 received", thread2_count, "frames")
print("serverMain received", frameServer.count, "frames")
