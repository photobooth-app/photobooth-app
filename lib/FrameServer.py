import json
from picamera2 import Picamera2
import psutil
import threading
from threading import Condition, Thread
import cv2
import time
from picamera2 import MappedArray


class FrameServer:
    def __init__(self, logger, ee, config):
        """A simple class that can serve up frames from one of the Picamera2's configured
        streams to multiple other threads.
        Pass in the Picamera2 object and the name of the stream for which you want
        to serve up frames."""
        self._picam2 = Picamera2()
        self._logger = logger
        self._config = config

        self._hq_array = None
        self._lores_array = None
        self._metadata = None
        self._hq_condition = Condition()
        self._lores_condition = Condition()
        self._trigger_hq_capture = False
        self._running = True
        self._currentmode = None
        self._count = 0
        self._fps = 0
        self._thread = Thread(name='FrameServerMainThread',
                              target=self._thread_func, daemon=True)
        self._statsthread = Thread(
            name='FrameServerStatsThread', target=self._statsthread_func, daemon=True)
        self._ee = ee

        # config HQ mode (used for picture capture and live preview on countdown)
        self._captureConfig = self._picam2.create_still_configuration(
            {"size": self._config.CAPTURE_CAM_RESOLUTION}, {"size": self._config.CAPTURE_VIDEO_RESOLUTION}, encode="lores", buffer_count=3, display="lores")

        # config preview mode (used for permanent live view)
        self._previewConfig = self._picam2.create_video_configuration(
            {"size": self._config.PREVIEW_CAM_RESOLUTION}, {"size": self._config.PREVIEW_VIDEO_RESOLUTION}, encode="lores", buffer_count=3, display="lores")

        # activate preview mode on init
        self._setConfigPreview()
        self._picam2.configure(self._currentmode)

        logger.info(f"camera_config: {self._picam2.camera_config}")
        logger.info(f"camera_controls: {self._picam2.camera_controls}")
        logger.info(f"controls: {self._picam2.controls}")

        tuning = Picamera2.load_tuning_file(config.CAMERA_TUNINGFILE)
        algo = self._picam2.find_tuning_algo(tuning, "rpi.agc")
        self._availAeExposureModes = (algo["exposure_modes"].keys())
        self._logger.info(
            f"AeExposureModes found in tuningfile: {self._availAeExposureModes}")

        self.setAeExposureMode(config.CAPTURE_EXPOSURE_MODE)

        # start camera
        self._picam2.start(show_preview=config.DEBUG_SHOWPREVIEW)

        # apply pre_callback overlay. whether there is actual content is decided in the callback itself.
        self._picam2.pre_callback = self._pre_callback_overlay

        # register to send initial data SSE
        self._ee.on("publishSSE/initial", self._publishSSEInitial)

        # when countdown starts change mode to HQ. after picture was taken change back.
        self._ee.on("onCountdownTakePicture",
                    self._setConfigCapture)

    def _setConfigCapture(self):
        self._lastmode = self._currentmode
        self._currentmode = self._captureConfig

    def _setConfigPreview(self):
        self._lastmode = self._currentmode
        self._currentmode = self._previewConfig

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

    def stop(self):
        """To stop the FrameServer, first stop any client threads (that might be
        blocked in wait_for_frame), then call this stop method. Don't stop the
        Picamera2 object until the FrameServer has been stopped."""
        self._running = False
        self._thread.join(1)
        self._statsthread.join(1)

        self._picam2.stop()

    def trigger_hq_capture(self):
        """switch one time to hq capture"""
        self._trigger_hq_capture = True

    def _statsthread_func(self):
        CALC_EVERY = 1  # update every x seconds only

        # FPS = 1 / time to process loop
        start_time = time.time()  # start time of the loop

        # to calc frames per second every second
        while self._running:
            if (time.time() > (start_time+CALC_EVERY)):
                self._fps = round(float(self._count) /
                                  (time.time() - start_time), 1)

                # reset
                self._count = 0
                start_time = time.time()

                # send metadata
                self._publishSSE_metadata()

            # thread wait otherwise 100% load ;)
            time.sleep(0.05)

    def _thread_func(self):
        while self._running:

            if (not self._currentmode == self._lastmode) and self._lastmode != None:
                self._logger.info(f"switch_mode invoked")
                self._picam2.switch_mode(self._currentmode)
                self._lastmode = self._currentmode

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

                self._ee.emit("onTakePicture")

                # capture hq picture
                (array,), self._metadata = self._picam2.capture_arrays(
                    ["main"])
                self._logger.debug(self._metadata)

                self._ee.emit("onTakePictureFinished")

                with self._hq_condition:
                    self._hq_array = array
                    self._hq_condition.notify_all()

                # switch back to preview mode
                self._setConfigPreview()

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

    def setAeExposureMode(self, newmode):
        self._logger.info(f"setAeExposureMode, try to set to {newmode}")
        try:
            newmode_Int = (
                list(self._availAeExposureModes).index(newmode.lower()))
            self._picam2.set_controls({"AeExposureMode": newmode_Int})
        except:
            self._logger.error(
                f"setAeExposureMode failed! Mode {newmode} not available")

        self._logger.info(
            f"current picam2.controls.get_libcamera_controls(): {self._picam2.controls.get_libcamera_controls()}")

    def _pre_callback_overlay(self, request):
        if self._config.DEBUG_OVERLAY:
            try:
                overlay1 = ""  # f"{focuser.get(focuser.OPT_FOCUS)} focus"
                overlay2 = f"{self.fps} fps"
                overlay3 = f"Exposure: {round(self._metadata['ExposureTime']/1000,1)}ms, 1/{int(1/(self._metadata['ExposureTime']/1000/1000))}s, resulting max fps: {round(1/self._metadata['ExposureTime']*1000*1000,1)}"
                overlay4 = f"Lux: {round(self._metadata['Lux'],1)}"
                overlay5 = f"Ae locked: {self._metadata['AeLocked']}, analogue gain {round(self._metadata['AnalogueGain'],1)}"
                overlay6 = f"Colour Temp: {self._metadata['ColourTemperature']}"
                overlay7 = f"cpu: 1/5/15min {[round(x / psutil.cpu_count() * 100,1) for x in psutil.getloadavg()]}%, active threads #{threading.active_count()}"
                colour = (210, 210, 210)
                origin1 = (30, 200)
                origin2 = (30, 230)
                origin3 = (30, 260)
                origin4 = (30, 290)
                origin5 = (30, 320)
                origin6 = (30, 350)
                origin7 = (30, 380)
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

    def _publishSSEInitial(self):
        self._publishSSE_metadata()

    def _publishSSE_metadata(self):
        self._ee.emit("publishSSE", sse_event="frameserver/metadata",
                      sse_data=json.dumps(self._metadata))
