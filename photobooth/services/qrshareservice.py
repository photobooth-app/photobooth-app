"""
https://photobooth-app.org/setup/shareservice/
"""

import json
import time
from uuid import UUID

import requests

from ..utils.stoppablethread import StoppableThread
from .baseservice import BaseService
from .config import appconfig
from .mediacollectionservice import MediacollectionService
from .sseservice import SseService


class QrShareService(BaseService):
    """_summary_"""

    def __init__(self, sse_service: SseService, mediacollection_service: MediacollectionService):
        super().__init__(sse_service)

        # objects
        self._mediacollection_service: MediacollectionService = mediacollection_service
        self._worker_thread: StoppableThread = None

    def start(self):
        super().start()

        if not appconfig.qrshare.enabled:
            self._logger.info("shareservice disabled, start aborted.")
            super().disabled()
            return

        self._worker_thread = StoppableThread(name="_shareservice_worker", target=self._worker_fun, daemon=True)
        self._worker_thread.start()

        self._logger.debug(f"{self.__module__} started - it tries to connect to dl.php on regular basis now.")

        super().started()

    def stop(self):
        super().stop()

        if self._worker_thread and self._worker_thread.is_alive():
            self._worker_thread.stop()
            self._worker_thread.join()

        super().stopped()

    def _worker_fun(self):
        # init
        self._logger.info("starting shareservice worker_thread")

        while not self._worker_thread.stopped():
            payload = {"action": "upload_queue"}
            try:
                r = requests.get(
                    appconfig.qrshare.shareservice_url,
                    params=payload,
                    stream=True,
                    timeout=8,
                    allow_redirects=False,
                )

                if r.ok:
                    self._logger.info("successfully connected to shareservice dl.php script")
                else:
                    raise RuntimeError(f"error connecting to shareservice dl.php, error {r.status_code} {r.text}")

            except requests.exceptions.ReadTimeout as exc:
                self._logger.warning(f"error connecting to service: {exc}")
                time.sleep(5)
                continue  # try again after wait time
            except Exception as exc:
                self._logger.error(f"unknown error occured: {exc}")
                time.sleep(10)
                continue  # try again after wait time

            if r.encoding is None:
                r.encoding = "utf-8"

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
                    try:
                        # if webserver not correctly setup, decoding might fail. catch exception mostly to inform user to debug
                        decoded_line: dict = json.loads(line)
                    except json.JSONDecodeError as exc:
                        self._logger.error(
                            f"webserver response from webserver malformed. please check qr shareservice url, "
                            f"webserver setup and webserver's logs. error: {exc}"
                            f"URL trying to connect is {appconfig.qrshare.shareservice_url}"
                        )
                        time.sleep(5)  # if url is wrong just slow down to not reconnect every second.
                        break

                    if decoded_line.get("file_identifier", None) and decoded_line.get("status", None):
                        # valid job check whether pending and upload
                        self._logger.info(f"got share upload job, {decoded_line}")

                        # set the file to be uploaded
                        request_upload_file = {}
                        try:
                            mediaitem_to_upload = self._mediacollection_service.db_get_image_by_id(UUID(decoded_line["file_identifier"]))
                            self._logger.info(f"found mediaitem to upload: {mediaitem_to_upload}")
                        except FileNotFoundError as exc:
                            self._logger.error(f"mediaitem not found, wrong id? {exc}")
                            self._logger.info("sending upload request to dl.php anyway to signal failure")
                        else:
                            self._logger.info(f"mediaitem to upload: {mediaitem_to_upload}")
                            if appconfig.qrshare.shareservice_share_original:
                                filepath_to_upload = mediaitem_to_upload.unprocessed
                            else:
                                filepath_to_upload = mediaitem_to_upload.processed

                            self._logger.debug(f"{filepath_to_upload=}")

                            request_upload_file = {"upload_file": open(filepath_to_upload, "rb")}

                        ## send request
                        start_time = time.time()

                        try:
                            r = requests.post(
                                appconfig.qrshare.shareservice_url,
                                files=request_upload_file,
                                data={
                                    "action": "upload",
                                    "apikey": appconfig.qrshare.shareservice_apikey,
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
