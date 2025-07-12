import logging
import tempfile
import time
import urllib.parse
from pathlib import Path
from threading import Condition

import requests

from ..config.groups.cameras import GroupCameraDigicamcontrol
from .abstractbackend import AbstractBackend, GeneralBytesResult

logger = logging.getLogger(__name__)


class DigicamcontrolBackend(AbstractBackend):
    r"""
    Digicamcontrol backend implementation

    Quirks:
        - using webfrontend only possible via IPv4! Sending requests first to localhost(IPV6) results in timeout,
          retry and a delay of 2 seconds on every request

    How to use Livestream
        - URL: http://localhost:5513/liveview.jpg
        - URL to simple digicamcontrol remoteapp: localhost:5513
        - start liveview:
        - http://localhost:5513/?CMD=LiveViewWnd_Show
        - http://localhost:5513/?CMD=All_Minimize  (issue at least one time to hide live preview, window should not popup on further liveview-starts)
        - stop liveview:
        - http://localhost:5513/?CMD=LiveViewWnd_Hide
        - capture from liveview (bad quality):
        - http://localhost:5513/?CMD=LiveView_Capture

    Capture photo

    via webinterface:
        - capture regular photo:
        http://localhost:5513/?slc=set&param1=session.folder&param2=c:\pictures
        http://localhost:5513/?slc=set&param1=session.filenametemplate&param2=capture1
        http://localhost:5513/?slc=capture&param1=&param2=
        - get session data for debugging:
        - http://localhost:5513/session.json
        - download photos:
        - specific file: http://localhost:5513/image/DSC_0001.jpg
        - last pic taken: http://localhost:5513/?slc=get&param1=lastcaptured&param2= ("returns a character if capture in progress")

    via remotecmd
        - capture regular photo:
        CameraControlRemoteCmd.exe /c capture c:\pictures\capture1.jpg

    """

    def __init__(self, config: GroupCameraDigicamcontrol):
        self._config: GroupCameraDigicamcontrol = config
        super().__init__(orientation=config.orientation)

        self._enabled_liveview: bool = False
        self._lores_data: GeneralBytesResult = GeneralBytesResult(data=b"", condition=Condition())

    def start(self):
        super().start()

    def stop(self):
        super().stop()

    def _wait_for_multicam_files(self) -> list[Path]:
        raise NotImplementedError("backend does not support multicam files")

    def _wait_for_still_file(self) -> Path:
        """
        for other threads to receive a hq JPEG image
        mode switches are handled internally automatically, no separate trigger necessary
        this function blocks until frame is received
        raise TimeoutError if no frame was received
        """
        with self._hires_data.condition:
            self._hires_data.request.set()

            if not self._hires_data.condition.wait(timeout=8):
                self._hires_data.request.clear()  # clear hq request even if failed, parent class might retry again
                raise TimeoutError("timeout receiving frames")

            assert self._hires_data.filepath
            return self._hires_data.filepath

    #
    # INTERNAL FUNCTIONS
    #

    def _wait_for_lores_image(self):
        """for other threads to receive a lores JPEG image"""
        self.pause_wait_for_lores_while_hires_capture()

        with self._lores_data.condition:
            if not self._lores_data.condition.wait(timeout=0.5):
                raise TimeoutError("timeout receiving frames")

            return self._lores_data.data

    def _on_configure_optimized_for_hq_capture(self):
        pass

    def _on_configure_optimized_for_hq_preview(self):
        pass

    def _on_configure_optimized_for_idle(self):
        pass

    def _on_configure_optimized_for_livestream_paused(self):
        pass

    def _enable_liveview(self):
        logger.debug("enable liveview and minimize windows")
        try:
            session = requests.Session()
            r = session.get(f"{self._config.base_url}/?CMD=LiveViewWnd_Show")
            r.raise_for_status()
            r = session.get(f"{self._config.base_url}/?CMD=All_Minimize")
            r.raise_for_status()
        except Exception as exc:
            logger.exception(exc)
            logger.error("fail set preview mode! no power? no connection?")
        else:
            logger.debug("set preview mode successful")

        self._enabled_liveview = True

    def setup_resource(self):
        self._enabled_liveview: bool = False

    def teardown_resource(self):
        # when stopping the backend also stop the livestream by following command.
        # if livestream is stopped, the camera is available to other processes again.
        session = requests.Session()
        session.get(f"{self._config.base_url}/?CMD=LiveViewWnd_Hide")
        # not raise_for_status, because we ignore and want to continue stopping the backend

    def run_service(self):
        # start in preview mode
        self._on_configure_optimized_for_idle()

        session = requests.Session()
        preview_failcounter = 0

        while not self._stop_event.is_set():  # repeat until stopped
            if self._hires_data.request.is_set():
                logger.debug("triggered capture")

                try:
                    # capture request, afterwards read file to buffer
                    tmp_dir = tempfile.gettempdir()

                    logger.info(f"requesting digicamcontrol to store files to {tmp_dir=}")

                    r = session.get(
                        f"{self._config.base_url}/?slc=set&param1=session.folder&param2={urllib.parse.quote(tmp_dir, safe='')}"  # noqa: E501
                    )
                    if r.text != "OK":
                        # text = r.text if (not r.headers.get("Content-Type") == "image/jpeg") else "IMAGE-data removed"
                        raise RuntimeError(f"error setting directory, status_code {r.status_code}, text: {r.text}")
                    r.raise_for_status()

                    r = session.get(f"{self._config.base_url}/?slc=capture&param1=&param2=")
                    r.raise_for_status()
                    if r.text != "OK":
                        # text = r.text if (not r.headers.get("Content-Type") == "image/jpeg") else "IMAGE-data removed"
                        raise RuntimeError(f"error capture, digicamcontrol exception, status_code {r.status_code}, text: {r.text}")

                    for attempt in range(10):
                        try:
                            # it could happen, that the http request finished, but the image is not yet fully processed. retry with little delay again
                            r = session.get(f"{self._config.base_url}/?slc=get&param1=lastcaptured&param2=")
                            r.raise_for_status()
                            if r.text in ("-", "?"):  # "-" means capture in progress, "?" means not yet an image captured
                                error_translation = {"-": "capture still in process", "?": "not yet an image captured"}
                                raise RuntimeError(f"error retrieving capture, status_code {r.status_code}, text: {error_translation[r.text]}")
                            else:
                                # at this point it's assumed that r.text holds the filename:
                                captured_filepath = Path(tmp_dir, r.text)
                                break  # no else below, its fine, proceed deliver image

                        except Exception as exc:
                            logger.warning(f"still waiting for picture, {attempt=}, retrying. error: {exc}")

                            time.sleep(0.3)
                            continue

                    else:
                        # we failed finally all the attempts - deal with the consequences.
                        logger.critical("finally failed after 10 attempts to capture image!")
                        raise RuntimeError("finally failed after 10 attempts to capture image!")

                    # success
                    with self._hires_data.condition:
                        self._hires_data.filepath = captured_filepath
                        self._hires_data.condition.notify_all()

                except Exception as exc:
                    logger.critical(f"error capture! check logs for errors. {exc}")

                finally:
                    # only capture one pic and return to lores streaming afterwards
                    self._hires_data.request.clear()

            else:
                # one time enable liveview
                if self.livestream_requested and not self._enabled_liveview:
                    self._enable_liveview()

                if self._enabled_liveview:
                    try:
                        # r = session.get("http://127.0.0.1:5514/live") #different port also!
                        r = session.get(f"{self._config.base_url}/liveview.jpg")
                        r.raise_for_status()

                        if self._lores_data.data and (self._lores_data.data == r.content):
                            raise RuntimeError(
                                "received same frame again - digicamcontrol liveview might be closed or delivers "
                                "low framerate only. Consider to reduce resolution or Livepreview Framerate."
                            )

                    except Exception as exc:
                        preview_failcounter += 1

                        if preview_failcounter <= 10:
                            logger.warning(f"error capturing frame from DSLR: {exc}")
                            # abort this loop iteration and continue sleeping...
                            time.sleep(0.5)  # add another delay to avoid flooding logs

                            continue  # continue and try in next run to get one...
                        else:
                            logger.critical(f"aborting capturing frame, camera disconnected? {exc}")
                            # stop device requested by leaving worker loop, so supvervisor can restart
                            break  # finally failed: exit worker fun, because no camera avail. connect fun supervises and reconnects
                    else:
                        preview_failcounter = 0

                    with self._lores_data.condition:
                        self._lores_data.data = r.content
                        self._lores_data.condition.notify_all()

                    self._frame_tick()

                    # limit fps to a reasonable amount. otherwise getting liveview.jpg would lead to 100% cpu as it's getting images way too often.
                    time.sleep(0.1)

            # wait for trigger...
            time.sleep(0.05)

        logger.warning("_worker_fun exits")
