"""
https://photobooth-app.org/setup/configuration/qrshareservice/
"""

import json
import logging
import tempfile
import time
from importlib import resources
from pathlib import Path
from threading import Event
from urllib.parse import quote
from uuid import UUID

import httpx2
from rclone_api.api import RcloneApi

from ...services.mediacollection.database import Database
from ...utils.resilientservice import QuietCrashReporter, ResilientService
from ...utils.stoppablethread import StoppableThread

logger = logging.getLogger(__name__)

API_PHP = "api.php"


class ShareOnDemandService(ResilientService):
    def __init__(self, rclone: RcloneApi, remote_name: str, remote_subdir: str, baseurl: str, apikey: str):

        # objects

        self._mediacollection_db: Database = Database()
        self._worker_thread: StoppableThread | None = None

        self.rclone: RcloneApi = rclone
        self.remote_name: str = remote_name
        self.remote_subdir: str = remote_subdir
        self.baseurl: str = baseurl
        self.apikey: str = apikey
        self.poll_every: int = 1

        self.shareservice_api_php_url = baseurl.rstrip("/") + "/" + API_PHP
        self.operational_flag = Event()

        super().__init__(crash_reporter=QuietCrashReporter(self.__class__.__name__))

    def __str__(self):
        return f"{self.__class__.__name__}"

    def start(self):
        self.operational_flag.clear()
        super().start()
        logger.debug(f"{self.__class__.__name__} started using endpoint baseurl {self.baseurl}.")

    def stop(self):
        self.operational_flag.clear()
        super().stop()

    def _is_online(self) -> bool:
        try:
            r = httpx2.head(self.baseurl, timeout=httpx2.Timeout(2))
            return r.status_code < 500
        except Exception:
            return False

    def _copy_frontend_to_remote(self):
        assert self.rclone

        api_source_path = Path(str(resources.files("web").joinpath("shareondemand/api.php")))
        assert api_source_path.is_file()

        # replace the default apikey by the chosen one
        content = api_source_path.read_text(encoding="utf-8")
        patched = content.replace("changedefault!", self.apikey, 1)  # count=1, only replace first occurence, keyword since 3.13 only

        # write patched version to a temp file
        with tempfile.NamedTemporaryFile("w", delete=False, encoding="utf-8") as tmp:
            tmp.write(patched)
            tmp_path = Path(tmp.name)

        logger.info(f"update api to {self.remote_name}{self.remote_subdir}")

        # add to queue for later upload.
        # this way if no internet the startup is not causing issues preventing the complete app from startup
        self.rclone.copyfile(
            tmp_path.parent.as_posix(),
            tmp_path.name,
            self.remote_name,
            Path(self.remote_subdir, api_source_path.name).as_posix(),
        )

        indexhtml_source_path = Path(str(resources.files("web").joinpath("sharepage/index.html")))
        assert indexhtml_source_path.is_file()

        self.rclone.copyfile(
            indexhtml_source_path.parent.as_posix(),
            indexhtml_source_path.name,
            self.remote_name,
            Path(self.remote_subdir, indexhtml_source_path.name).as_posix(),
        )

    def get_share_link(self, identifier: UUID, revision: int) -> str:
        logger.debug(f"generating shareondemand qr links for {identifier}")

        # qr share service with api.php:
        # this is to the index.html displaying the portal
        download_portal_url = f"{self.baseurl.rstrip('/')}/#/?url="
        # this delivers the actual file (no html around).
        mediaitem_url = f"{self.baseurl.rstrip('/')}/{API_PHP}?action=download&id={identifier}&rev={revision}"

        return download_portal_url + quote(mediaitem_url, safe="")

    def setup_resource(self):
        """setup the resource right before run_service logic"""

        logger.info("starting ShareOnDemand worker_thread")

        if not self._is_online():
            raise ConnectionError(f"no connection to host {self.baseurl}, cannot start shareondemand service")

        self._copy_frontend_to_remote()

        self.operational_flag.set()

    def teardown_resource(self):
        """tear down the resource right after run_service logic and in case of crashes"""

    def run_service(self):
        """service logic to be run when the service is started"""

        # outer while loop: connect to uploadqueue-stream
        while not self._stop_event.is_set():
            queue_response = None

            try:
                queue_response = httpx2.post(
                    self.shareservice_api_php_url,
                    data={"action": "getpendingjob", "apikey": self.apikey},
                    timeout=httpx2.Timeout(5),
                )

                queue_response.raise_for_status()

                decoded_queue = queue_response.json()

                # logger.debug(f"server message: {decoded_queue}")

            except json.JSONDecodeError:
                logger.error(
                    f"webserver response from webserver malformed. please check qr shareservice url, "
                    f"webserver setup and webserver's logs."
                    f"URL trying to connect is {self.shareservice_api_php_url}, response is: "
                    f"{queue_response.text if queue_response else 'unknown'}"
                )
                raise
            except httpx2.TimeoutException as exc:
                logger.warning(f"timeout connecting to service: {exc}")
                raise
            except httpx2.HTTPStatusError as exc:
                logger.error(f"server error code {exc.response.status_code} for req URL {exc.request.url}: {exc.response.text}")

                raise

            except Exception as exc:
                logger.error(f"unknown error occured: {exc}")
                raise

            upload_id: str | None = decoded_queue.get("id", None)
            if upload_id:
                # valid job check whether pending and upload
                logger.debug(f"got upload job, id {upload_id}")

                # ACK senden
                httpx2.post(
                    self.shareservice_api_php_url,
                    data={"action": "accept", "apikey": self.apikey, "id": upload_id},
                    timeout=5,
                )

                # set the file to be uploaded
                request_upload_file = {}
                file_handle = None
                try:
                    mediaitem_id = UUID(upload_id.split("_", maxsplit=1)[0])
                    mediaitem_to_upload = self._mediacollection_db.get_item(mediaitem_id)
                    logger.info(f"Uploading {mediaitem_to_upload}")

                    file_handle = open(mediaitem_to_upload.processed, "rb")
                    request_upload_file = {"upload_file": file_handle}
                except Exception as exc:
                    logger.error(f"Mediaitem not found, error: {exc}. Sending upload request to api.php anyway to signal failure")

                ## send request
                start_time = time.time()
                r_upload = None

                try:
                    r_upload = httpx2.post(
                        self.shareservice_api_php_url,
                        files=request_upload_file,
                        data={"action": "upload", "apikey": self.apikey, "id": upload_id},
                        timeout=9,
                        # follow_redirects=False,
                    )
                    r_upload.raise_for_status()

                except httpx2.HTTPStatusError as exc:
                    logger.warning(f"upload failed {exc.response.status_code}: {exc.response.text}")
                    # try again?
                except Exception as exc:
                    logger.warning(f"upload failed, err: {exc}")
                    # try again?
                else:
                    logger.debug(f"upload took {round((time.time() - start_time), 2)}s, answer from server: {r_upload.text}")
                finally:
                    if file_handle is not None:
                        file_handle.close()

            elif decoded_queue.get("ping", None):
                pass

            else:
                logger.error(f"invalid queue message, ignore: {decoded_queue}")

            if self._stop_event.is_set():
                break

            time.sleep(self.poll_every)

        logger.info("leaving shareservice workerthread")
