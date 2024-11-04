import logging

from wigglecam_connector.models import ConfigPool as GroupBackendWigglecam
from wigglecam_connector.node import Node
from wigglecam_connector.pool import Pool

from .abstractbackend import AbstractBackend

logger = logging.getLogger(__name__)


class WigglecamBackend(AbstractBackend):
    """Virtual camera backend to test photobooth"""

    def __init__(self, config: GroupBackendWigglecam):
        self._config: GroupBackendWigglecam = config
        super().__init__()

        self._camera_pool: Pool = None

    def _device_start(self):
        nodes = []
        for config_node in self._config.nodes:
            node = Node(config=config_node)
            nodes.append(node)

        self._camera_pool: Pool = Pool(nodes=nodes)

        logger.debug(f"{self.__module__} started")

    def _device_stop(self):
        logger.debug(f"{self.__module__} stopped")

    def _device_available(self) -> bool:
        raise NotImplementedError

    def _wait_for_hq_image(self):
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
