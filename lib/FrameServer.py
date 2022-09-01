from threading import Condition, Thread
import cv2
import simplejpeg
import time


class FrameServer:
    def __init__(self, picam2, logger, CONFIG):
        """A simple class that can serve up frames from one of the Picamera2's configured
        streams to multiple other threads.
        Pass in the Picamera2 object and the name of the stream for which you want
        to serve up frames."""
        self._picam2 = picam2
        self._logger = logger
        self._CONFIG = CONFIG
        self._hq_array = None
        self._lores_array = None
        self._metadata = None
        self._lores_convert_to_jpeg = True
        self._hq_condition = Condition()
        self._lores_condition = Condition()
        self._trigger_hq_capture = False
        self._running = True
        self._count = 0
        self._fps = 0
        self._thread = Thread(target=self._thread_func, daemon=True)

    @property
    def count(self):
        """A count of the number of frames received."""
        return self._count

    @property
    def fps(self):
        """frames per second"""
        return self._fps

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

            # to calc frames per second
            start_time = time.time()  # start time of the loop

            if not self._trigger_hq_capture:
                (array,), self._metadata = self._picam2.capture_arrays(
                    ["lores"])

                if self._lores_convert_to_jpeg:
                    rgb = cv2.cvtColor(array, cv2.COLOR_YUV420p2RGB)
                    buf = simplejpeg.encode_jpeg(
                        rgb, quality=self._CONFIG.LORES_QUALITY, colorspace='BGR', colorsubsampling='420')
                    size = len(buf)
                    self._logger.debug(
                        f'mjpeg conversion active, jpeg size: {round(size/1000, 1)} kb')

                    array = buf

                with self._lores_condition:
                    self._lores_array = array
                    self._lores_condition.notify_all()
            else:
                # only capture one pic and return to lores streaming afterwards
                self._trigger_hq_capture = False

                # capture hq picture
                (array,), self._metadata = self._picam2.capture_arrays(
                    ["main"])
                self._logger.debug(self._metadata)
                with self._hq_condition:
                    self._hq_array = array
                    self._hq_condition.notify_all()

            # FPS = 1 / time to process loop
            self._fps = round(1.0 / (time.time() - start_time), 1)
            self._logger.debug(
                f"{self._fps} fps")

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
