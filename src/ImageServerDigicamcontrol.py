import requests.packages.urllib3.util.connection as urllib3_cn
import socket
import urlsrc.parse
import requests
from PIL import Image, ImageGrab
import tempfile
import os
from io import BytesIO
from threading import Condition
import time
import logging
from pymitter import EventEmitter
import ImageServerAbstract
import StoppableThread
from ConfigSettings import settings
logger = logging.getLogger(__name__)


def allowed_gai_family():
    family = socket.AF_INET    # force IPv4
    return family


urllib3_cn.allowed_gai_family = allowed_gai_family


class ImageServerDigicamcontrol(ImageServerAbstract.ImageServerAbstract):
    """
    # Backend for Digicamcontrol.
    ## Configuration of Digicamcontrol:
      - enable webserver, ...
      - TODO.
    ## Quirks:
      - using digicamera webfrontend only possible via IPv4! Sending requests first to localhost(IPV6) results in timeout, retry and log delay via requests


    ## How to use Livestream
      - URL: http://localhost:5513/liveview.jpg
      - URL to simple digicamcontrol remoteapp: localhost:5513
      - start liveview:
        - http://localhost:5513/?CMD=LiveViewWnd_Show
        - http://localhost:5513/?CMD=All_Minimize  (issue at least one time to hide live preview, window should not popup on further liveview-starts)
      - stop liveview:
        - http://localhost:5513/?CMD=LiveViewWnd_Hide
      - capture from liveview (bad quality):
        - http://localhost:5513/?CMD=LiveView_Capture
    ## capture photo
    ### via webinterface:
      - capture regular photo:
        http://localhost:5513/?slc=set&param1=session.folder&param2=c:\pictures
        http://localhost:5513/?slc=set&param1=session.filenametemplate&param2=capture1
        http://localhost:5513/?slc=capture&param1=&param2=
      - get session data for debugging:
        - http://localhost:5513/session.json
      - download photos:
        - specific file: http://localhost:5513/image/DSC_0001.jpg
        - last pic taken: http://localhost:5513/?slc=get&param1=lastcaptured&param2= ("returns a character if capture in progress")
    ### via remotecmd
      - capture regular photo:
        CameraControlRemoteCmd.exe /c capture c:\pictures\capture1.jpg

    ### Identified workflow:
      start:
      - start live view
      - minimize windows
      use:
      - capture 1...n
      - read file
      (seems liveview is kept on even when capture)
      stop:
      - stop live view
    """

    def __init__(self, ee, enableStream):
        super().__init__(ee, enableStream)

        # public props (defined in abstract class also)
        self.exif_make = "Photobooth FrameServer Digicamcontrol"
        self.exif_model = "Custom"
        self.metadata = {}  # TODO: Exif shall be transferred from original camera picture

        # private props
        self._hq_img_buffer = None
        self._hq_condition = Condition()
        self._trigger_hq_capture = False

        self._generateImagesThread = StoppableThread.StoppableThread(name="_generateImagesThread",
                                                                     target=self._GenerateImagesFun, daemon=True)

    def start(self):
        """To start the FrameServer"""
        self._generateImagesThread.start()
        self._onPreviewMode()
        logger.debug(f"{self.__module__} started")

    def stop(self):
        """To stop the FrameServer"""
        self._generateImagesThread.stop()
        logger.debug(f"{self.__module__} stopped")

    def wait_for_hq_image(self):
        """for other threads to receive a hq JPEG image"""
        with self._hq_condition:
            while True:
                # TODO: timeout needs to be handled properly and adjusted per backend well!
                if not self._hq_condition.wait(1):
                    raise IOError("timeout receiving frames")
                return self._hq_img_buffer.getvalue()

    def gen_stream(self):
        raise NotImplementedError(
            "CMD backend does not support native livestreaming.")

    def trigger_hq_capture(self):
        self._onCaptureMode()
        self._trigger_hq_capture = True

    """
    INTERNAL FUNCTIONS
    """

    def _wait_for_lores_image(self):
        """for other threads to receive a lores JPEG image"""
        raise NotImplementedError()

    def _wait_for_autofocus_frame(self):
        """autofocus not supported by this backend"""
        raise NotImplementedError()

    def _onCaptureMode(self):
        logger.debug(
            "change to capture mode - nothing needs to be done actually")

    def _onPreviewMode(self):
        logger.debug("enable liveview and minimize windows")
        r = requests.get("http://127.0.0.1:5513/?CMD=LiveViewWnd_Show")
        # there is currently no way to check the result of these requests unfortunately. weird implementation in webserver it seems.
        # if not r.text == "OK":
        #    raise Exception(f"error starting preview {r.text}")

        r = requests.get("http://127.0.0.1:5513/?CMD=All_Minimize")
        # if not r.text == "OK":
        #    raise Exception(f"error starting preview {r.text}")

    """
    INTERNAL IMAGE GENERATOR
    """

    def _GenerateImagesFun(self):
        counter = 0

        while not self._generateImagesThread.stopped():  # repeat until stopped
            counter += 1

            if self._trigger_hq_capture:
                # only capture one pic and return to lores streaming afterwards
                self._trigger_hq_capture = False

                self._onCaptureMode()

                logger.debug(
                    "triggered capture")

                self._ee.emit("frameserver/onCapture")

                # capture request, afterwards read file to buffer
                tmp_dir = tempfile.gettempdir()
                tmp_filepath = tempfile.mktemp(
                    prefix='booth_',
                    suffix='',
                    dir=tmp_dir)
                tmp_filename = os.path.basename(tmp_filepath)
                logger.info(f"tmp_dir={tmp_dir}, tmp_filename={tmp_filename}")
                session = requests.Session()
                r = session.get(
                    f"http://127.0.0.1:5513/?slc=set&param1=session.folder&param2={urlsrc.parse.quote(tmp_dir, safe='')}")
                if not r.text == "OK":
                    raise IOError(f"error setting directory {r.text}")

                r = session.get(
                    f"http://127.0.0.1:5513/?slc=set&param1=session.filenametemplate&param2={urlsrc.parse.quote(tmp_filename, safe='')}")
                if not r.text == "OK":
                    raise IOError(f"error setting filename {r.text}")

                r = session.get(
                    "http://127.0.0.1:5513/?slc=capture&param1=&param2=")
                if not r.text == "OK":
                    raise IOError(f"error capture {r.text}")

                logger.info(f"saved camera file to f{tmp_filepath}.jpg")
                with open(f"{tmp_filepath}.jpg", "rb") as fh:
                    jpeg_buffer = BytesIO(fh.read())

                self._ee.emit("frameserver/onCaptureFinished")

                # TODO: get metadata

                with self._hq_condition:
                    self._hq_img_buffer = jpeg_buffer
                    self._hq_condition.notify_all()

                # switch back to preview mode
                self._onPreviewMode()

            # wait for trigger...
            time.sleep(0.05)
        return
