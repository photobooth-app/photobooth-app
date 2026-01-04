from pathlib import Path

import niquests
import pytest

# from photobooth.plugins.synchronizer_rclone.dto import Priority, PriorizedTask, SyncTaskDelete, SyncTaskUpload
from photobooth.plugins.synchronizer_rclone.config import Common, SynchronizerConfig
from photobooth.plugins.synchronizer_rclone.synchronizer_rclone import SynchronizerRclone


@pytest.fixture()
def synchronizer(tmp_path: Path):
    # setup
    synchronizer = SynchronizerRclone()
    synchronizer._config = SynchronizerConfig(
        common=Common(enabled=True),
    )

    synchronizer.ensure_rclone_avail()

    yield synchronizer


def test_start_runs_components(synchronizer: SynchronizerRclone):
    with pytest.raises(niquests.exceptions.ConnectionError):
        niquests.post("http://localhost:5572/rc/noop")

    synchronizer.start()

    synchronizer.wait_until_ready()

    resp = niquests.post("http://localhost:5572/rc/noop", json={"test": "data"})

    assert resp.ok
    assert resp.json() == {"test": "data"}

    synchronizer.stop()

    with pytest.raises(niquests.exceptions.ConnectionError):
        niquests.post("http://localhost:5572/rc/noop")
