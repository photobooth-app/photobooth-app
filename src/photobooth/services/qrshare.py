"""
https://photobooth-app.org/setup/shareservice/
"""

import json
import logging
import time
from typing import Any
from urllib.parse import quote
from uuid import UUID

import requests

from ..appconfig import appconfig
from ..utils.stoppablethread import StoppableThread
from .base import BaseService
from .collection import MediacollectionService

logger = logging.getLogger(__name__)


class QrShareService(BaseService):
    """_summary_"""

    def __init__(self, mediacollection_service: MediacollectionService):
        super().__init__()

        # objects
        self._mediacollection_service: MediacollectionService = mediacollection_service
        self._worker_thread: StoppableThread | None = None

        self.shareservice_dl_php_url = appconfig.qrshare.shareservice_url + "/dl.php"

    def start(self):
        super().start()

        if not appconfig.qrshare.enabled:
            logger.info("shareservice disabled, start aborted.")
            super().disabled()
            return

        self._worker_thread = StoppableThread(name="_shareservice_worker", target=self._worker_fun, daemon=True)
        self._worker_thread.start()

        logger.debug(f"{self.__class__.__name__} started - it tries to connect to dl.php on regular basis now.")

        super().started()

    def stop(self):
        super().stop()

        if self._worker_thread and self._worker_thread.is_alive():
            self._worker_thread.stop()
            self._worker_thread.join()

        super().stopped()

    def get_share_link(self, identifier: UUID, filename: str) -> list[str]:
        logger.debug(f"generating qr share links for {identifier} {filename}")

        out_links: list[str] = []

        # qr share service with dl.php:
        if appconfig.qrshare.enabled:
            # this is to the index.html displaying the portal
            download_portal_url = f"{appconfig.qrshare.shareservice_url.rstrip('/')}/#/?url="
            # this delivers the actual file (no html around).
            mediaitem_url = f"{appconfig.qrshare.shareservice_url.rstrip('/')}/dl.php?action=download&id={str(identifier)}"

            out_links.append(download_portal_url + quote(mediaitem_url, safe=""))

        if appconfig.qrshare.enabled_custom:
            custom_url = appconfig.qrshare.share_custom_qr_url
            custom_url = custom_url.replace("{filename}", filename)
            custom_url = custom_url.replace("{identifier}", str(identifier))

            out_links.append(custom_url)

        return out_links

    def _worker_fun(self):
        assert self._worker_thread
        # init
        logger.info("starting shareservice worker_thread")

        while not self._worker_thread.stopped():
            payload = {
                "action": "upload_queue",
                "apikey": appconfig.qrshare.shareservice_apikey,
            }
            try:
                r = requests.post(
                    self.shareservice_dl_php_url,
                    data=payload,
                    stream=True,
                    timeout=8,
                    allow_redirects=False,
                )

                if r.ok:
                    logger.info("successfully connected to shareservice dl.php script")
                else:
                    raise RuntimeError(f"error connecting to shareservice dl.php, error {r.status_code} {r.text}")

            except requests.exceptions.ReadTimeout as exc:
                logger.warning(f"error connecting to service: {exc}")
                time.sleep(5)
                continue  # try again after wait time
            except Exception as exc:
                logger.error(f"unknown error occured: {exc}")
                time.sleep(10)
                continue  # try again after wait time

            if r.encoding is None:
                r.encoding = "utf-8"

            iterator = r.iter_lines(chunk_size=24, decode_unicode=True)

            while not self._worker_thread.stopped():
                try:
                    line = next(iterator)
                except StopIteration:
                    logger.debug("dl.php script finished after some time. stopiteration issued-reconnect")
                    break
                except Exception as exc:
                    logger.warning(f"encountered shareservice connection issue. retrying. error: {exc}")
                    break

                # filter out keep-alive new lines
                if line:
                    try:
                        # if webserver not correctly setup, decoding might fail. catch exception mostly to inform user to debug
                        decoded_line: dict[str, Any] = json.loads(line)
                    except json.JSONDecodeError as exc:
                        logger.error(
                            f"webserver response from webserver malformed. please check qr shareservice url, "
                            f"webserver setup and webserver's logs. error: {exc}"
                            f"URL trying to connect is {self.shareservice_dl_php_url}"
                        )
                        time.sleep(5)  # if url is wrong just slow down to not reconnect every second.
                        break

                    if decoded_line.get("file_identifier", None) and decoded_line.get("status", None):
                        # valid job check whether pending and upload
                        logger.info(f"got share upload job, {decoded_line}")

                        # set the file to be uploaded
                        request_upload_file = {}
                        try:
                            mediaitem_to_upload = self._mediacollection_service.get_item(UUID(decoded_line["file_identifier"]))
                            logger.info(f"found mediaitem to upload: {mediaitem_to_upload}")
                        except Exception as exc:
                            logger.error(f"mediaitem not found, error: {exc}")
                            logger.info("sending upload request to dl.php anyway to signal failure")
                        else:
                            logger.info(f"mediaitem to upload: {mediaitem_to_upload}")
                            request_upload_file = {"upload_file": open(mediaitem_to_upload.processed, "rb")}

                        ## send request
                        start_time = time.time()

                        try:
                            r = requests.post(
                                self.shareservice_dl_php_url,
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
                            logger.warning(f"upload failed, err: {exc}")
                            # try again?

                        else:
                            logger.debug(f"response from dl.php script: {r.text}")
                            logger.debug(f"-- request took: {round((time.time() - start_time), 2)}s")
                    elif decoded_line.get("ping", None):
                        pass
                    else:
                        logger.error(f"invalid queue line, ignore: {line}")

                # if a keepalive message is issued, we can check here also regularly for exit condition set
                if self._worker_thread.stopped():
                    logger.debug("stop workerthread requested")
                    break

            if not self._worker_thread.stopped():
                # usually dl.php finishes after several minutes and the client needs to reconnect again.
                logger.info("restarting loop wait 1 second")
                time.sleep(1)

        logger.info("leaving shareservice workerthread")
