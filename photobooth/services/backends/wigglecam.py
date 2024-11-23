import logging
import time
from pathlib import Path
from tempfile import NamedTemporaryFile
from threading import Condition

import requests
from wigglecam.connector import CameraNode, CameraPool
from wigglecam.connector.dto import ConnectorJobRequest
from wigglecam.connector.models import ConfigCameraPool

from ...utils.stoppablethread import StoppableThread
from ..config.groups.backends import GroupBackendWigglecam
from .abstractbackend import AbstractBackend, GeneralBytesResult

logger = logging.getLogger(__name__)


class WigglecamBackend(AbstractBackend):
    """Virtual camera backend to test photobooth"""

    def __init__(self, config: GroupBackendWigglecam):
        self._config: GroupBackendWigglecam = config

        super().__init__()

        self._camera_pool: CameraPool = None

        # worker threads
        self._worker_thread: StoppableThread = None

        self._lores_data: GeneralBytesResult = GeneralBytesResult(data=None, condition=Condition())

    def _device_start(self):
        nodes = []
        for config_node in self._config.nodes:
            node = CameraNode(config=config_node)
            nodes.append(node)

        self._config_camera_pool = ConfigCameraPool(**self._config.model_dump())  # extract the campoolconfig from wiggle element
        self._camera_pool: CameraPool = CameraPool(ConfigCameraPool, nodes=nodes)

        logger.info(self._camera_pool.get_nodes_status())
        logger.info(self._camera_pool.is_healthy())

        self._worker_thread = StoppableThread(name="digicamcontrol_worker_thread", target=self._worker_fun, daemon=True)
        self._worker_thread.start()

        logger.debug(f"{self.__module__} started")

    def _device_stop(self):
        if self._worker_thread and self._worker_thread.is_alive():
            self._worker_thread.stop()
            self._worker_thread.join()

        logger.debug(f"{self.__module__} stopped")

    def _device_available(self) -> bool:
        return True
        # TODO: need something to check? Like:  return self._camera_pool.is_healthy()

    def _wait_for_multicam_files(self) -> list[Path]:
        camerapooljobrequest = ConnectorJobRequest(number_captures=1)

        try:
            connectorjobitem = self._camera_pool.setup_and_trigger_pool(camerapooljobrequest=camerapooljobrequest)
            self._camera_pool.wait_until_all_finished_ok(connectorjobitem)

            downloadresult = self._camera_pool.download_all(connectorjobitem)
            logger.info(downloadresult)
            logger.info(f"this is from node[0], first item: {downloadresult.node_mediaitems[0].mediaitems[0].filepath}")

        except Exception as exc:
            logger.error(f"Error processing: {exc}")
            logger.info(self._camera_pool.get_nodes_status_formatted())
            raise exc
        else:
            # currently only number_captures=1 supported, so we just take the first index from result
            out = [x.mediaitems[0].filepath for x in downloadresult.node_mediaitems]

            return out

    def _wait_for_still_file(self) -> Path:
        with NamedTemporaryFile(mode="wb", delete=False, dir="tmp", prefix="wigglecam_", suffix=".jpg") as f:
            f.write(self._camera_pool._nodes[self._config.index_backend_stills].camera_still())

            return Path(f.name)

    def _wait_for_lores_image(self):
        return self._camera_pool._nodes[self._config.index_backend_video].camera_still()
        # """for other threads to receive a lores JPEG image"""
        # with self._lores_data.condition:
        #     if not self._lores_data.condition.wait(timeout=0.5):
        #         raise TimeoutError("timeout receiving frames")

        #     return self._lores_data.data

    def _on_configure_optimized_for_idle(self):
        pass

    def _on_configure_optimized_for_hq_preview(self):
        pass

    def _on_configure_optimized_for_hq_capture(self):
        pass

    #
    # INTERNAL IMAGE GENERATOR
    #
    def _worker_fun(self):
        logger.debug("starting digicamcontrol worker function")

        # start in preview mode
        self._on_configure_optimized_for_idle()

        session_live = requests.Session()
        preview_failcounter = 0

        while not self._worker_thread.stopped():  # repeat until stopped
            time.sleep(1)
            # TODO: maybe maybe.

        logger.warning("_worker_fun exits")
