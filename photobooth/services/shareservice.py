"""
https://mgrl.github.io/photobooth-docs/extras/shareservice/
"""

import json
import time

import requests
from pymitter import EventEmitter

from ..appconfig import AppConfig
from ..utils.stoppablethread import StoppableThread
from .baseservice import BaseService
from .mediacollectionservice import MediacollectionService


class ShareService(BaseService):
    """_summary_"""

    def __init__(self, evtbus: EventEmitter, config: AppConfig, mediacollection_service: MediacollectionService):
        super().__init__(evtbus, config)

        # objects
        self._mediacollection_service: MediacollectionService = mediacollection_service
        self._initialized: bool = False
        self._worker_thread = StoppableThread(name="_shareservice_worker", target=self._worker_fun, daemon=True)

        # registered events
        # self._evtbus.on("publishSSE/initial", self._on_stats_interval_timer)

        self._logger.info("initialized share service")

    def _initialize(self):
        self._initialized = False

        self._logger.info("checking shareservice api endpoint")
        r = requests.get(self._config.common.shareservice_url, params={"action": "info"})
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
        if not self._config.common.shareservice_enable:
            self._logger.info("shareservice disabled, start aborted.")
            return
        self._initialize()
        if self._initialized:
            self._worker_thread.start()
        else:
            self._logger.error("shareservice init was not successful. start service aborted.")

    def stop(self):
        """_summary_"""
        self._worker_thread.stop()
        if self._worker_thread.is_alive():
            self._worker_thread.join()

    def _worker_fun(self):
        # init
        # nothing here yet

        while not self._worker_thread.stopped():
            payload = {"action": "upload_queue"}
            r = requests.get(self._config.common.shareservice_url, params=payload, stream=True, timeout=60)
            if r.encoding is None:
                r.encoding = "utf-8"

            iterator = r.iter_lines(decode_unicode=True)

            while not self._worker_thread.stopped():
                try:
                    line = next(iterator)
                except Exception as exc:
                    print(exc)
                    self._logger.warning(f"encountered shareservice connection issue. retrying. error: {exc}")
                    break

                # filter out keep-alive new lines
                if line:
                    job = json.loads(line)

                    if job.get("file_identifier", None) and job.get("status", None):
                        # valid job check whether pending and upload
                        self._logger.info(f"got share upload job, {job}")

                        # set the file to be uploaded
                        try:
                            mediaitem_to_upload = self._mediacollection_service.db_get_image_by_id(
                                job["file_identifier"]
                            )
                        except FileNotFoundError as exc:
                            self._logger.error(f"mediaitem not found, wrong id? {exc}")
                            self._logger.info("sending upload request to dl.php anyway to signal failure")
                            request_upload_file = {}
                        else:
                            self._logger.info(f"found mediaitem to upload: {mediaitem_to_upload}")
                            if self._config.common.shareservice_share_original:
                                filepath_to_upload = mediaitem_to_upload.path_original
                            else:
                                filepath_to_upload = mediaitem_to_upload.path_full
                            self._logger.debug(f"{filepath_to_upload=}")

                            request_upload_file = {"upload_file": open(filepath_to_upload, "rb")}
                        finally:
                            start_time = time.time()

                            r = requests.post(
                                self._config.common.shareservice_url,
                                files=request_upload_file,
                                params={
                                    "action": "upload",
                                    "apikey": self._config.common.shareservice_apikey,
                                    "id": job["file_identifier"],
                                },
                            )

                            self._logger.debug(f"response from php server: {r.text}")
                            self._logger.debug(f"-- request took: {round((time.time() - start_time), 2)}s")

                    else:
                        self._logger.error(f"invalid queue line, ignore: {line}")
                else:
                    # if a keepalive message is issued, we can check here also regularly for exit condition set
                    if self._worker_thread.stopped():
                        self._logger.debug("stop workerthread requested")
                        break

            self._logger.info("request timed out or aborted otherwise, restarting loop after 5 seconds")
            time.sleep(5)
