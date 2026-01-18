from pathlib import Path
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from photobooth.plugins.synchronizer_rclone.config import SynchronizerConfig
from photobooth.plugins.synchronizer_rclone.synchronizer_rclone import SynchronizerRclone
from photobooth.plugins.synchronizer_rclone.types import TaskCopy, TaskDelete


@pytest.fixture
def sync():
    """Create a SynchronizerRclone with mocked config + mocked rclone client."""
    s = SynchronizerRclone()

    cfg = SynchronizerConfig()
    cfg.common.enabled = True
    cfg.common.enabled_share_links = True
    cfg.common.enabled_custom_qr_url = True
    cfg.common.custom_qr_url = "http://test123"

    # Enable first remote for all sync types
    remote = cfg.remotes[0]
    remote.enabled = True
    remote.enable_regular_sync = True
    remote.enable_immediate_sync = True
    remote.enable_sharepage_sync = True
    remote.shareconfig.enabled = True
    remote.shareconfig.use_sharepage = False

    s._config = cfg

    s._rclone_client = MagicMock()

    return s


# ---------------------------------------------------------------------------
# start() / stop()
# ---------------------------------------------------------------------------


def test_service_real():
    sr = SynchronizerRclone()

    cfg = SynchronizerConfig()
    cfg.common.enabled = True

    sr._config = cfg

    sr.start()
    sr.wait_until_ready()

    sr.stop()


# ---------------------------------------------------------------------------
# _put_to_rclone_job_manager()
# ---------------------------------------------------------------------------


def test_put_to_rclone_copy(sync: SynchronizerRclone):
    sync.is_running = lambda: True

    task = TaskCopy(Path("/local/file.txt"), Path("remote/file.txt"))
    sync._put_to_rclone_job_manager(task)

    sync._rclone_client.copyfile_async.assert_called_once()  # type: ignore


def test_put_to_rclone_delete(sync: SynchronizerRclone):
    sync.is_running = lambda: True

    task = TaskDelete(Path("remote/file.txt"))
    sync._put_to_rclone_job_manager(task)

    sync._rclone_client.deletefile.assert_called_once()  # type: ignore


# ---------------------------------------------------------------------------
# get_share_links()
# ---------------------------------------------------------------------------


def test_get_share_links_public(sync: SynchronizerRclone):
    sync.is_running = lambda: True

    sync._rclone_client.publiclink.return_value.link = "https://remote/link"  # type: ignore

    out = sync.get_share_links(Path("media/file.jpg"), uuid4())
    assert out == ["http://test123", "https://remote/link"]


def test_get_share_links_public_failure(sync):
    sync.is_running = lambda: True

    sync._rclone_client.publiclink.side_effect = Exception("boom")

    out = sync.get_share_links(Path("media/file.jpg"), uuid4())
    assert out == ["http://test123"]


# ---------------------------------------------------------------------------
# get_stats()
# ---------------------------------------------------------------------------


def test_get_stats_ok(sync: SynchronizerRclone):
    mock_client = sync._rclone_client

    mock_client.core_stats.return_value = MagicMock(  # type: ignore
        bytes=100,
        totalBytes=200,
        eta=10,
        errors=0,
        speed=1024 * 1024,
        totalTransfers=5,
        deletes=1,
        lastError="",
        transferring=[],
    )

    mock_client.job_list.return_value = MagicMock(runningIds=[5])  # type: ignore

    stats = sync.get_stats()

    assert stats is not None
    assert stats.name == "Synchronizer"


def test_get_stats_error(sync: SynchronizerRclone):
    sync._rclone_client.core_stats.side_effect = Exception("fail")  # type: ignore

    stats = sync.get_stats()

    assert stats is not None
    assert stats.stats[0].name == "Error"


# ---------------------------------------------------------------------------
# _copy_sharepage_to_remotes()
# ---------------------------------------------------------------------------


def test_copy_sharepage_to_remotes(sync: SynchronizerRclone):
    # Patch resources.files("web").joinpath("sharepage/index.html")
    with patch("photobooth.plugins.synchronizer_rclone.synchronizer_rclone.resources.files") as mock_files:
        # Make joinpath return a real file path (this test file)
        mock_files.return_value.joinpath.return_value = Path(__file__)

        sync._copy_sharepage_to_remotes()

        sync._rclone_client.copyfile_async.assert_called_once()  # type: ignore


# ---------------------------------------------------------------------------
# collection_* hooks
# ---------------------------------------------------------------------------


def test_collection_hooks(sync: SynchronizerRclone):
    with patch.object(sync, "_put_to_rclone_job_manager") as mock_put:
        f = Path("media/test.jpg")

        sync.collection_original_file_added([f])
        sync.collection_files_added([f])
        sync.collection_files_updated([f])
        sync.collection_files_deleted([f])

        assert mock_put.call_count == 4
