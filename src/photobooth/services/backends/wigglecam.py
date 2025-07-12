import logging
import time
from pathlib import Path
from tempfile import NamedTemporaryFile
from threading import Condition

import requests
from wigglecam.connector import CameraNode, CameraPool
from wigglecam.connector.dto import ConnectorJobRequest
from wigglecam.connector.models import ConfigCameraPool

from ...utils.helper import filename_str_time
from ...utils.stoppablethread import StoppableThread
from ..config.groups.cameras import GroupCameraWigglecam
from .abstractbackend import AbstractBackend, GeneralBytesResult

logger = logging.getLogger(__name__)


class WigglecamBackend(AbstractBackend):
    def __init__(self, config: GroupCameraWigglecam):
        self._config: GroupCameraWigglecam = config
        super().__init__()

        self._camera_pool: CameraPool | None = None

        self._lores_data: GeneralBytesResult = GeneralBytesResult(data=b"", condition=Condition())
        self._worker_thread: StoppableThread | None = None

    def start(self):
        super().start()

    def stop(self):
        super().stop()

    def _wait_for_multicam_files(self) -> list[Path]:
        assert self._camera_pool
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
        if not self._camera_pool:
            time.sleep(0.2)  # add short delay because otherwise it's requested another still immediately.
            raise RuntimeError("backend is not started yet, so it cannot deliver stills.")

        with NamedTemporaryFile(mode="wb", delete=False, dir="tmp", prefix=f"{filename_str_time()}_wigglecam_", suffix=".jpg") as f:
            f.write(self._camera_pool._nodes[self._config.index_cam_stills].camera_still())

            return Path(f.name)

    def _wait_for_lores_image(self):
        """for other threads to receive a lores JPEG image"""

        # alternative could be some kind of streaming proxy, but I did not find out yet how to prevent server from
        # stalling if a request is still open to the stream...
        # @router.get("/stream_proxy.mjpg")
        # def video_stream_proxy():
        #     async def iterfile():
        #         async with httpx.AsyncClient() as client:
        #             async with client.stream("GET", "http://wigglecam-dev3:8010/api/camera/stream.mjpg") as r:
        #                 async for chunk in r.aiter_bytes():
        #                     yield chunk

        #     return StreamingResponse(iterfile(), media_type="multipart/x-mixed-replace; boundary=frame")

        self.pause_wait_for_lores_while_hires_capture()

        with self._lores_data.condition:
            if not self._lores_data.condition.wait(timeout=0.5):
                raise TimeoutError("timeout receiving frames")

            return self._lores_data.data

    def _on_configure_optimized_for_idle(self):
        pass

    def _on_configure_optimized_for_hq_preview(self):
        pass

    def _on_configure_optimized_for_hq_capture(self):
        pass

    def _on_configure_optimized_for_livestream_paused(self):
        pass

    def setup_resource(self):
        # quick sanity check.
        max_index = max(self._config.index_cam_stills, self._config.index_cam_video)
        if max_index > len(self._config.nodes) - 1:
            raise RuntimeError(f"configuration error: index out of range! {max_index=} whereas max_index allowed={len(self._config.nodes) - 1}")

        nodes = []
        for config_node in self._config.nodes:
            node = CameraNode(config=config_node)
            nodes.append(node)

        self._config_camera_pool = ConfigCameraPool(**self._config.model_dump())  # extract the campoolconfig from wiggle element
        self._camera_pool = CameraPool(ConfigCameraPool, nodes=nodes)

        logger.info(self._camera_pool.get_nodes_status())
        logger.info(f"pool healthy: {self._camera_pool.is_healthy()}")

    def teardown_resource(self):
        pass

    def run_service(self):
        while not self._stop_event.is_set():
            if self.livestream_requested:
                try:
                    r = requests.get(
                        f"{self._config.nodes[self._config.index_cam_video].base_url}/api/camera/stream.mjpg", stream=True, timeout=(2, 5)
                    )
                    r.raise_for_status()
                except Exception as exc:
                    time.sleep(1)
                    logger.error(f"error requesting stream, keep trying. error: {exc}")
                    continue

                bytes = b""
                for chunk in r.iter_content(chunk_size=1024):
                    bytes += chunk
                    a = bytes.find(b"\xff\xd8")
                    b = bytes.find(b"\xff\xd9")
                    if a != -1 and b != -1:
                        jpeg_bytes = bytes[a : b + 2]
                        bytes = bytes[b + 2 :]

                        # notify about jpg
                        with self._lores_data.condition:
                            self._lores_data.data = jpeg_bytes
                            self._lores_data.condition.notify_all()

                        self._frame_tick()

                    if self._stop_event.is_set():
                        break
            else:
                time.sleep(0.1)

        logger.info("_worker_fun left")
