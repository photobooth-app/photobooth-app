import logging
import time
from pathlib import Path

import pytest

from photobooth.appconfig import appconfig
from photobooth.services.synchronizer.config import (
    Backend,
    FilesystemBackendConfig,
    FilesystemConnectorConfig,
    FilesystemShareConfig,
)
from photobooth.services.synchronizer.synchronizer import Synchronizer

logger = logging.getLogger(name=None)


@pytest.fixture()
def synchronizer_plugin(tmp_path: Path):
    appconfig.synchronizer.common.enabled = True
    appconfig.synchronizer.backends = [
        Backend(
            enabled=True,
            backend_config=FilesystemBackendConfig(
                connector=FilesystemConnectorConfig(target_dir=tmp_path),
                share=FilesystemShareConfig(),
            ),
        ),
    ]

    # setup
    synchronizer = Synchronizer()

    yield synchronizer


def test_init(synchronizer_plugin: Synchronizer):
    synchronizer_plugin.start()

    time.sleep(1)

    synchronizer_plugin.stop()
