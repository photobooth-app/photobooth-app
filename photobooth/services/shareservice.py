"""
https://photobooth-app.org/extras/shareservice/
"""

import json
import time

import requests

from ..appconfig import AppConfig
from ..utils.stoppablethread import StoppableThread
from .baseservice import BaseService
from .mediacollectionservice import MediacollectionService
from .sseservice import SseService


class ShareService(BaseService):
    """_summary_"""

    def __init__(self, config: AppConfig, sse_service: SseService, mediacollection_service: MediacollectionService):
        super().__init__(config, sse_service)

        # objects
        self._mediacollection_service: MediacollectionService = mediacollection_service
        self._initialized: bool = False
        self._worker_thread = StoppableThread(name="_shareservice_worker", target=self._worker_fun, daemon=True)

    def _initialize(self):
        self._initialized = False

        self._logger.info("checking shareservice api endpoint")
        try:
            r = requests.get(self._config.sharing.shareservice_url, params={"action": "info"}, timeout=10, allow_redirects=False)
        except Exception as exc:
            self._logger.warning(f"error checking shareservice api endpoint: {exc}")
        else:
            if r.status_code == 200:
                try:
                    info = r.json()
                    self._logger.info(f"{info=}")
                except requests.exceptions.JSONDecodeError as exc:
                    self._logger.error(f"api endpoint error: {exc}")

                self._initialized = True
                self._logger.info("api endpoint found, URL valid")
            else:
                self._logger.error("api endpoint check failed")

    def start(self):
        """_summary_"""
        if not self._config.sharing.shareservice_enabled:
            self._logger.info("shareservice disabled, start aborted.")
            return
        self._initialize()
        if self._initialized:
            self._worker_thread.start()

            # short sleep until workerthread is started and likely to be connected to service or failed.
            time.sleep(1)

            self._logger.debug(f"{self.__module__} initialized and started")
        else:
            self._logger.error("shareservice init was not successful. start service aborted.")

    def stop(self):
        """_summary_"""
        self._worker_thread.stop()
        if self._worker_thread.is_alive():
            self._worker_thread.join()

    def _worker_fun(self):
        # init
        self._logger.info("starting shareservice worker_thread")

        while not self._worker_thread.stopped():
            payload = {"action": "upload_queue"}
            try:
                r = requests.get(
                    self._config.sharing.shareservice_url,
                    params=payload,
                    stream=True,
                    timeout=8,
                    allow_redirects=False,
                )
            except requests.exceptions.ReadTimeout as exc:
                self._logger.warning(f"error connecting to service: {exc}")
                time.sleep(5)
                continue  # try again after wait time
            except Exception as exc:
                self._logger.error(f"unknown error occured: {exc}")
                time.sleep(5)
                continue  # try again after wait time

            if r.encoding is None:
                r.encoding = "utf-8"

            if r.status_code == 200:
                self._logger.info("successfully connected to shareservice dl.php script")
            else:
                self._logger.error("problem connecting to shareservice dl.php script!")
                break  # this is implied to be permanent error, break to exit worker fun

            iterator = r.iter_lines(chunk_size=24, decode_unicode=True)

            while not self._worker_thread.stopped():
                try:
                    line = next(iterator)
                except StopIteration:
                    self._logger.debug("dl.php script finished after some time. stopiteration issued-reconnect")
                    break
                except Exception as exc:
                    self._logger.warning(f"encountered shareservice connection issue. retrying. error: {exc}")
                    break

                # filter out keep-alive new lines
                if line:
                    decoded_line = json.loads(line)

                    if decoded_line.get("file_identifier", None) and decoded_line.get("status", None):
                        # valid job check whether pending and upload
                        self._logger.info(f"got share upload job, {decoded_line}")

                        # set the file to be uploaded
                        request_upload_file = {}
                        try:
                            mediaitem_to_upload = self._mediacollection_service.db_get_image_by_id(decoded_line["file_identifier"])
                            self._logger.info(f"found mediaitem to upload: {mediaitem_to_upload}")
                        except FileNotFoundError as exc:
                            self._logger.error(f"mediaitem not found, wrong id? {exc}")
                            self._logger.info("sending upload request to dl.php anyway to signal failure")
                        else:
                            self._logger.info(f"mediaitem to upload: {mediaitem_to_upload}")
                            if self._config.sharing.shareservice_share_original:
                                filepath_to_upload = mediaitem_to_upload.path_original
                            else:
                                filepath_to_upload = mediaitem_to_upload.path_full

                            self._logger.debug(f"{filepath_to_upload=}")

                            request_upload_file = {"upload_file": open(filepath_to_upload, "rb")}

                        ## send request
                        start_time = time.time()

                        try:
                            r = requests.post(
                                self._config.sharing.shareservice_url,
                                files=request_upload_file,
                                data={
                                    "action": "upload",
                                    "apikey": self._config.sharing.shareservice_apikey,
                                    "id": decoded_line["file_identifier"],
                                },
                                timeout=9,
                                allow_redirects=False,
                            )
                        except Exception as exc:
                            self._logger.warning(f"upload failed, err: {exc}")
                            # try again?

                        else:
                            self._logger.debug(f"response from dl.php script: {r.text}")
                            self._logger.debug(f"-- request took: {round((time.time() - start_time), 2)}s")
                    elif decoded_line.get("ping", None):
                        pass
                    else:
                        self._logger.error(f"invalid queue line, ignore: {line}")

                # if a keepalive message is issued, we can check here also regularly for exit condition set
                if self._worker_thread.stopped():
                    self._logger.debug("stop workerthread requested")
                    break

            self._logger.info("request timed out, error occured or shutdown requested")
            if not self._worker_thread.stopped():
                self._logger.info("restarting loop wait 1 second")
                time.sleep(1)

        self._logger.info("leaving shareservice workerthread")
