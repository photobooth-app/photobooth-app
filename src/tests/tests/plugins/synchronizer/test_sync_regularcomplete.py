import logging
import time
from pathlib import Path

import pytest

from photobooth.plugins.synchronizer.config import (
    Backend,
    Common,
    FilesystemBackendConfig,
    FilesystemConnectorConfig,
    FilesystemShareConfig,
    SynchronizerConfig,
)
from photobooth.plugins.synchronizer.synchronizer import Synchronizer

logger = logging.getLogger(name=None)


@pytest.fixture()
def synchronizer_plugin(tmp_path: Path):
    # setup
    synchronizer = Synchronizer()
    synchronizer._config = SynchronizerConfig(
        common=Common(enabled=True),
        backends=[
            Backend(
                enabled=True,
                backend_config=FilesystemBackendConfig(
                    connector=FilesystemConnectorConfig(target_dir=tmp_path),
                    share=FilesystemShareConfig(),
                ),
            ),
        ],
    )

    yield synchronizer


def test_init(synchronizer_plugin: Synchronizer):
    synchronizer_plugin.start()

    time.sleep(1)

    synchronizer_plugin.stop()
