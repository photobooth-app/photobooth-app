from pathlib import Path
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from photobooth.plugins.synchronizer.config import RemoteConfig, ShareConfig, SynchronizerConfig
from photobooth.plugins.synchronizer.immediate_synchronizer import ThreadedImmediateSyncPipeline
from photobooth.plugins.synchronizer.regular_synchronizer import ThreadedRegularSync
from photobooth.plugins.synchronizer.synchronizer import Synchronizer
from photobooth.plugins.synchronizer.types import DeleteOperation, TaskDelete


@pytest.fixture(scope="function")
def sync():
    """Create a SynchronizerRclone with mocked config + mocked rclone client."""

    with (
        patch("photobooth.plugins.synchronizer.synchronizer.RcloneApi") as mock_rclone_ctor,
        patch("photobooth.plugins.synchronizer.synchronizer.ThreadedImmediateSyncPipeline") as mock_pipeline_ctor,
    ):
        mock_client = MagicMock()
        mock_pipeline = MagicMock()

        mock_rclone_ctor.return_value = mock_client
        mock_pipeline_ctor.return_value = mock_pipeline

        s = Synchronizer()

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

        s.start()
        s.wait_until_ready()
        # time.sleep(1)

        yield s

        s.stop()


# ---------------------------------------------------------------------------
# start() / stop()
# ---------------------------------------------------------------------------


def test_service_real():
    sr = Synchronizer()

    cfg = SynchronizerConfig()
    cfg.common.enabled = True

    sr._config = cfg

    sr.start()
    sr.wait_until_ready()

    sr.stop()


# ---------------------------------------------------------------------------
# get_share_links()
# ---------------------------------------------------------------------------


def test_get_share_links_public(sync: Synchronizer):

    sync._rclone_client.publiclink.return_value.link = "https://remote/link"  # type: ignore

    out = sync.get_share_links(Path("media/file.jpg"), uuid4())
    assert out == ["http://test123", "https://remote/link"]


def test_get_share_links_public_failure(sync):

    sync._rclone_client.publiclink.side_effect = Exception("boom")

    out = sync.get_share_links(Path("media/file.jpg"), uuid4())
    assert out == ["http://test123"]


# ---------------------------------------------------------------------------
# get_stats()
# ---------------------------------------------------------------------------


def test_get_stats_ok(sync: Synchronizer):
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


def test_get_stats_error(sync: Synchronizer):
    sync._rclone_client.core_stats.side_effect = Exception("fail")  # type: ignore

    stats = sync.get_stats()

    assert stats is not None
    assert stats.stats[0].name == "Error"


# ---------------------------------------------------------------------------
# _copy_sharepage_to_remotes()
# ---------------------------------------------------------------------------
def test_copy_sharepage_to_remotes(sync: Synchronizer):
    # Patch resources.files("web").joinpath("sharepage/index.html")
    with patch("photobooth.plugins.synchronizer.synchronizer.resources.files") as mock_files:
        # Make joinpath return a real file path (this test file)
        mock_files.return_value.joinpath.return_value = Path(__file__)
        r = sync._config.remotes[0]
        before_calls = sync._rclone_client.copyfile_async.call_count  # type: ignore
        sync._copy_sharepage_to_remotes(remote=r)
        assert sync._rclone_client.copyfile_async.call_count == before_calls + 1  # type: ignore


# ---------------------------------------------------------------------------
# collection_* hooks
# ---------------------------------------------------------------------------


def test_collection_hooks(sync: Synchronizer):
    with patch.object(sync._immediate_pipeline, "submit") as mock_put:
        f = Path("media/test.jpg")

        sync.collection_files_added([f], priority_modifier=0)
        sync.collection_files_updated([f])
        sync.collection_files_deleted([f])

        assert mock_put.call_count == 3


def test_immediateSnycPipeline_skip_delete_op_when_upload_only_is_enabled():
    remotes = [
        RemoteConfig(enabled=True, description="backup", name="backup:", subdir="archive", copy_only_mode=True, shareconfig=ShareConfig()),
        RemoteConfig(enabled=True, description="sync", name="sync:", subdir="archive", copy_only_mode=False, shareconfig=ShareConfig()),
    ]

    pipeline = ThreadedImmediateSyncPipeline(rclone=MagicMock(), remotes=remotes, max_concurrency=0)
    pipeline.submit(TaskDelete(Path("media/test.jpg")), priority=19)

    assert len(pipeline.results) == 1
    assert pipeline.queue.qsize() == 1

    queued_job = pipeline.queue.get_nowait()
    assert isinstance(queued_job.operation, DeleteOperation)
    assert queued_job.operation.dst_fs == "sync:"
    assert queued_job.operation.dst_remote == "archive/media/test.jpg"


def test_regularSync_uses_copy_for_upload_only_remotes():
    remotes = [
        RemoteConfig(enabled=True, description="backup", name="backup:", subdir="archive", copy_only_mode=True, shareconfig=ShareConfig()),
        RemoteConfig(enabled=True, description="sync", name="sync:", subdir="archive", copy_only_mode=False, shareconfig=ShareConfig()),
    ]

    rclone = MagicMock()
    rclone.copy_async.return_value = MagicMock(jobid=11)
    rclone.sync_async.return_value = MagicMock(jobid=22)

    regular_sync = ThreadedRegularSync(rclone=rclone, fullsync_remotes=remotes, sync_interval_s=999)
    regular_sync._worker.join(timeout=1)
    regular_sync.stop()

    assert rclone.copy_async.call_count == 1
    assert rclone.sync_async.call_count == 1
    assert rclone.wait_for_jobs.call_count == 1
    assert rclone.wait_for_jobs.call_args.args[0] == [11, 22]


@pytest.mark.parametrize(
    "bucket,subdir,expected",
    [
        ("", "", ""),
        ("", "archive", "archive"),
        ("mybucket", "", "mybucket"),
        ("mybucket", "photos/event1", "mybucket/photos/event1"),
        ("/mybucket/", "/photos/", "mybucket/photos"),
        ("mybucket", r"photos\event1", "mybucket/photos/event1"),
    ],
)
def test_remoteconfig_base_path(bucket, subdir, expected):
    r = RemoteConfig(name="s3:", bucket=bucket, subdir=subdir, shareconfig=ShareConfig())
    assert r.base_path == expected


def test_immediateSyncPipeline_uses_bucket_in_paths():
    remotes = [RemoteConfig(enabled=True, name="s3:", bucket="mybucket", subdir="photos", shareconfig=ShareConfig())]

    rclone = MagicMock()
    pipeline = ThreadedImmediateSyncPipeline(rclone=rclone, remotes=remotes, max_concurrency=0)
    pipeline.submit(TaskDelete(Path("media/test.jpg")), priority=19)

    rclone.ls.assert_called_once_with("s3:", "mybucket/photos")
    assert pipeline.queue.get_nowait().operation.dst_remote == "mybucket/photos/media/test.jpg"


def test_immediateSyncPipeline_creates_missing_bucket():
    remotes = [RemoteConfig(enabled=True, name="s3:", bucket="mybucket", subdir="photos", shareconfig=ShareConfig())]

    rclone = MagicMock()
    rclone.ls.side_effect = _process_exc()
    pipeline = ThreadedImmediateSyncPipeline(rclone=rclone, remotes=remotes, max_concurrency=0)
    pipeline.submit(TaskDelete(Path("media/test.jpg")), priority=19)

    rclone.mkdir.assert_called_once_with("s3:", "mybucket/photos")
    assert pipeline.queue.qsize() == 1


def test_immediateSyncPipeline_skips_missing_path_without_bucket():
    remotes = [RemoteConfig(enabled=True, name="usb:", subdir="drive", shareconfig=ShareConfig())]

    rclone = MagicMock()
    rclone.ls.side_effect = _process_exc()
    pipeline = ThreadedImmediateSyncPipeline(rclone=rclone, remotes=remotes, max_concurrency=0)
    pipeline.submit(TaskDelete(Path("media/test.jpg")), priority=19)

    rclone.mkdir.assert_not_called()
    assert pipeline.queue.qsize() == 0


def test_immediateSyncPipeline_skips_when_bucket_creation_fails():
    remotes = [RemoteConfig(enabled=True, name="s3:", bucket="mybucket", shareconfig=ShareConfig())]

    rclone = MagicMock()
    rclone.ls.side_effect = _process_exc()
    rclone.mkdir.side_effect = Exception("access denied")
    pipeline = ThreadedImmediateSyncPipeline(rclone=rclone, remotes=remotes, max_concurrency=0)
    pipeline.submit(TaskDelete(Path("media/test.jpg")), priority=19)

    assert pipeline.queue.qsize() == 0


def test_regularSync_ensures_bucket_and_syncs_into_it():
    remotes = [RemoteConfig(enabled=True, name="s3:", bucket="mybucket", subdir="photos", shareconfig=ShareConfig())]

    rclone = MagicMock()
    rclone.sync_async.return_value = MagicMock(jobid=1)

    regular_sync = ThreadedRegularSync(rclone=rclone, fullsync_remotes=remotes, sync_interval_s=999)
    regular_sync._worker.join(timeout=1)
    regular_sync.stop()

    rclone.mkdir.assert_called_once_with("s3:", "mybucket/photos")
    assert rclone.sync_async.call_args.args[1] == "s3:mybucket/photos/media"


def test_regularSync_skips_remote_if_bucket_creation_fails():
    remotes = [RemoteConfig(enabled=True, name="s3:", bucket="mybucket", shareconfig=ShareConfig())]

    rclone = MagicMock()
    rclone.mkdir.side_effect = Exception("access denied")

    regular_sync = ThreadedRegularSync(rclone=rclone, fullsync_remotes=remotes, sync_interval_s=999)
    regular_sync._worker.join(timeout=1)
    regular_sync.stop()

    assert rclone.sync_async.call_count == 0


def test_regularSync_does_not_create_path_without_bucket():
    remotes = [RemoteConfig(enabled=True, name="sync:", subdir="archive", shareconfig=ShareConfig())]

    rclone = MagicMock()
    rclone.sync_async.return_value = MagicMock(jobid=1)

    regular_sync = ThreadedRegularSync(rclone=rclone, fullsync_remotes=remotes, sync_interval_s=999)
    regular_sync._worker.join(timeout=1)
    regular_sync.stop()

    rclone.mkdir.assert_not_called()
    assert rclone.sync_async.call_args.args[1] == "sync:archive/media"


def test_sharepage_and_publiclink_use_bucket(sync: Synchronizer):
    remote = sync._config.remotes[0]
    remote.name = "s3:"
    remote.bucket = "mybucket"
    remote.subdir = "photos"

    sync._copy_sharepage_to_remotes(remote)
    assert sync._rclone_client.copyfile_async.call_args.args[3] == "mybucket/photos/index.html"  # type: ignore

    remote.shareconfig.enabled = True
    remote.shareconfig.use_sharepage = False
    sync._rclone_client.publiclink.return_value.link = "https://remote/link"  # type: ignore
    sync.get_share_links(Path("media/test.jpg"), uuid4())
    assert sync._rclone_client.publiclink.call_args.args[1] == "mybucket/photos/media/test.jpg"  # type: ignore


def _process_exc():
    from rclone_api.exceptions import RcloneProcessException

    exc = RcloneProcessException.__new__(RcloneProcessException)
    Exception.__init__(exc, "not found")
    exc.status = 404
    return exc
