import logging

from wigglecam.connector import CameraNode, CameraPool
from wigglecam.connector.models import ConfigCameraPool

from .abstractbackend import AbstractBackend

logger = logging.getLogger(__name__)


class WigglecamBackend(AbstractBackend):
    """Virtual camera backend to test photobooth"""

    def __init__(self, config: ConfigCameraPool):
        self._config: ConfigCameraPool = config
        super().__init__()

        self._camera_pool: CameraPool = None

    def _device_start(self):
        nodes = []
        for config_node in self._config.nodes:
            node = CameraNode(config=config_node)
            nodes.append(node)

        self._camera_pool: CameraPool = CameraPool(nodes=nodes)

        logger.debug(f"{self.__module__} started")

    def _device_stop(self):
        logger.debug(f"{self.__module__} stopped")

    def _device_available(self) -> bool:
        return True
        # TODO: need something to check? Like:  return self._camera_pool.is_healthy()

    def _wait_for_hq_image(self):
        # TODO: here we stitch the nodes images already and create a gif/mp4/whatever is best. because the system expects just one system

        raise NotImplementedError

    #
    # INTERNAL FUNCTIONS
    #

    def _wait_for_lores_image(self):
        raise NotImplementedError

    def _on_configure_optimized_for_idle(self):
        pass

    def _on_configure_optimized_for_hq_preview(self):
        pass

    def _on_configure_optimized_for_hq_capture(self):
        pass
