import psutil
import threading
from threading import Condition, Thread
import cv2
import time
from picamera2 import MappedArray

face_detector = cv2.CascadeClassifier(
    "/usr/share/opencv4/haarcascades/haarcascade_frontalface_default.xml")


class FrameServer:
    def __init__(self, picam2, logger, notifier, CONFIG):
        """A simple class that can serve up frames from one of the Picamera2's configured
        streams to multiple other threads.
        Pass in the Picamera2 object and the name of the stream for which you want
        to serve up frames."""
        self._picam2 = picam2
        self._logger = logger
        #self._infoled = infoled
        self._CONFIG = CONFIG
        self._hq_array = None
        self._lores_array = None
        self._metadata = None
        self._hq_condition = Condition()
        self._lores_condition = Condition()
        self._trigger_hq_capture = False
        self._running = True
        self._count = 0
        self._fps = 0
        self._thread = Thread(target=self._thread_func, daemon=True)
        self._statsthread = Thread(target=self._statsthread_func, daemon=True)
        self._facedetectionthread = Thread(
            target=self._FacedetectionThread, daemon=True)

        self._notifier = notifier

        if CONFIG.DEBUG:
            self._picam2.pre_callback = self.apply_overlay

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
        self._statsthread.start()
        # self._facedetectionthread.start()

    def stop(self):
        """To stop the FrameServer, first stop any client threads (that might be
        blocked in wait_for_frame), then call this stop method. Don't stop the
        Picamera2 object until the FrameServer has been stopped."""
        self._running = False
        self._thread.join(1)
        self._statsthread.join(1)
        # self._facedetectionthread.join(1)

    def trigger_hq_capture(self):
        """switch one time to hq capture"""
        self._trigger_hq_capture = True

    def _statsthread_func(self):
        CALC_EVERY = 2  # update every x seconds only

        # FPS = 1 / time to process loop
        start_time = time.time()  # start time of the loop

        # to calc frames per second every second
        while self._running:
            if (time.time() > (start_time+CALC_EVERY)):
                self._fps = round(float(self._count) /
                                  (time.time() - start_time), 1)
                self._logger.debug(f"{self._fps} fps")

                # reset
                self._count = 0
                start_time = time.time()

            # thread wait otherwise 100% load ;)
            time.sleep(0.05)

    def _FacedetectionThread(self):
        # TODO, could be used for autofocus on faces. slow.
        while self._running:
            frame = self.wait_for_lores_frame()
            grey = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)
            faces = face_detector.detectMultiScale(grey,       scaleFactor=1.1,
                                                   minNeighbors=5,
                                                   minSize=(60, 60),
                                                   maxSize=(500, 600))

            for (x, y, w, h) in faces:
                cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0))

            cv2.imshow("faces", frame)

            print("faces", faces)

            time.sleep(1)

    def _thread_func(self):
        while self._running:

            if not self._trigger_hq_capture:
                (orig_array,), self._metadata = self._picam2.capture_arrays(
                    ["lores"])

                # convert colors to rgb because lores-stream is always YUV420 that is not used in application usually.
                array = cv2.cvtColor(orig_array, cv2.COLOR_YUV420p2RGB)

                with self._lores_condition:
                    self._lores_array = array
                    self._lores_condition.notify_all()
            else:
                # only capture one pic and return to lores streaming afterwards
                self._trigger_hq_capture = False

                self._notifier.raise_event("onTakePicture")

                # capture hq picture
                (array,), self._metadata = self._picam2.capture_arrays(
                    ["main"])
                self._logger.debug(self._metadata)

                # algorithm way too slow for raspi (takes minutes :( )
                #array = cv2.fastNlMeansDenoisingColored(array, None, 5, 5, 7, 21)

                self._notifier.raise_event("onTakePictureFinished")

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

    def apply_overlay(self, request):
        try:
            overlay1 = ""  # f"{focuser.get(focuser.OPT_FOCUS)} focus"
            overlay2 = f"{self.fps} fps"
            overlay3 = f"Exposure time: {self._metadata['ExposureTime']}us, resulting max fps: {round(1/self._metadata['ExposureTime']*1000*1000,1)}"
            overlay4 = f"Lux: {round(self._metadata['Lux'],1)}"
            overlay5 = f"Ae locked: {self._metadata['AeLocked']}, analogue gain {self._metadata['AnalogueGain']}"
            overlay6 = f"Colour Temp: {self._metadata['ColourTemperature']}"
            overlay7 = f"cpu: {psutil.cpu_percent()}%, loadavg {[round(x / psutil.cpu_count() * 100,1) for x in psutil.getloadavg()]}, thread active count {threading.active_count()}"
            colour = (210, 210, 210)
            origin1 = (10, 200)
            origin2 = (10, 230)
            origin3 = (10, 260)
            origin4 = (10, 290)
            origin5 = (10, 320)
            origin6 = (10, 350)
            origin7 = (10, 380)
            font = cv2.FONT_HERSHEY_SIMPLEX
            scale = 1
            thickness = 2

            with MappedArray(request, "lores") as m:
                cv2.putText(m.array, overlay1, origin1,
                            font, scale, colour, thickness)
                cv2.putText(m.array, overlay2, origin2,
                            font, scale, colour, thickness)
                cv2.putText(m.array, overlay3, origin3,
                            font, scale, colour, thickness)
                cv2.putText(m.array, overlay4, origin4,
                            font, scale, colour, thickness)
                cv2.putText(m.array, overlay5, origin5,
                            font, scale, colour, thickness)
                cv2.putText(m.array, overlay6, origin6,
                            font, scale, colour, thickness)
                cv2.putText(m.array, overlay7, origin7,
                            font, scale, colour, thickness)
        except:
            # fail silent if metadata still None (TODO: change None to Metadata contructor on init in Frameserver)
            pass
