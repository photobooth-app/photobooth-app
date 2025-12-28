from pathlib import Path
from unittest.mock import MagicMock

import pytest
from pydantic import HttpUrl

from photobooth.plugins.synchronizer_legacy.config import (
    Backend,
    Common,
    FilesystemBackendConfig,
    FilesystemConnectorConfig,
    FilesystemShareConfig,
    SynchronizerConfig,
)
from photobooth.plugins.synchronizer_legacy.synchronizer_legacy import SynchronizerLegacy
from photobooth.plugins.synchronizer_legacy.types import Priority, PriorizedTask, SyncTaskDelete, SyncTaskUpload


@pytest.fixture()
def synchronizer(tmp_path: Path):
    # setup
    synchronizer = SynchronizerLegacy()
    synchronizer._config = SynchronizerConfig(
        common=Common(enabled=True),
        backends=[
            Backend(
                enabled=True,
                backend_config=FilesystemBackendConfig(
                    connector=FilesystemConnectorConfig(target_dir=tmp_path),
                    share=FilesystemShareConfig(media_url=HttpUrl("http://test.dummy.local/remote/")),
                ),
            ),
        ],
    )

    yield synchronizer


def test_reset(synchronizer: SynchronizerLegacy):
    synchronizer._queue_processors = [MagicMock()]
    synchronizer._regular_complete_sync = [MagicMock()]
    synchronizer._shares = [MagicMock()]

    synchronizer.reset()

    assert synchronizer._queue_processors == []
    assert synchronizer._regular_complete_sync == []
    assert synchronizer._shares == []


def test_start_runs_components(synchronizer: SynchronizerLegacy):
    synchronizer.start()

    assert len(synchronizer._queue_processors) == 1
    assert len(synchronizer._regular_complete_sync) == 1
    assert len(synchronizer._shares) == 1


def test_stop_calls_stop_on_all(synchronizer: SynchronizerLegacy):
    q1 = MagicMock()
    q2 = MagicMock()
    r1 = MagicMock()
    r2 = MagicMock()
    synchronizer._queue_processors = [q1, q2]
    synchronizer._regular_complete_sync = [r1, r2]

    synchronizer.stop()

    for i in [q1, q2, r1, r2]:
        i.stop.assert_called_once()


def test_put_to_workers_queues(synchronizer: SynchronizerLegacy):
    mock_worker = MagicMock()
    synchronizer._queue_processors = [mock_worker]
    task = PriorizedTask(Priority.HIGH, MagicMock())

    synchronizer._put_to_processors_queues(task)

    mock_worker.put_to_queue.assert_called_once_with(task)


def test_get_share_links_enabled(synchronizer: SynchronizerLegacy):
    synchronizer.start()

    result = synchronizer.get_share_links(Path("media/file.jpg"))

    assert result == ["http://test.dummy.local/remote/#/?url=http%3A%2F%2Ftest.dummy.local%2Fremote%2Ffile.jpg"]


def test_get_share_links_disabled(synchronizer: SynchronizerLegacy):
    synchronizer._config.common.enable_share_links = False
    synchronizer.start()

    result = synchronizer.get_share_links(Path("media/file.txt"))
    assert result == []


def test_collection_files_added(synchronizer: SynchronizerLegacy):
    mock_worker = MagicMock()
    synchronizer._queue_processors = [mock_worker]
    files = [Path("media/file1.txt"), Path("media/file2.txt")]

    synchronizer.collection_files_added(files)

    assert mock_worker.put_to_queue.call_count == 2
    calls = [call.args[0] for call in mock_worker.put_to_queue.call_args_list]
    for c in calls:
        assert isinstance(c, PriorizedTask)
        assert isinstance(c.task, SyncTaskUpload)
        assert c.priority == Priority.HIGH


def test_collection_files_original_added(synchronizer: SynchronizerLegacy):
    mock_worker = MagicMock()
    synchronizer._queue_processors = [mock_worker]
    files = [Path("media/file1.txt"), Path("media/file2.txt")]

    synchronizer.collection_original_file_added(files)

    assert mock_worker.put_to_queue.call_count == 2
    calls = [call.args[0] for call in mock_worker.put_to_queue.call_args_list]
    for c in calls:
        assert isinstance(c, PriorizedTask)
        assert isinstance(c.task, SyncTaskUpload)
        assert c.priority == Priority.LOW


def test_collection_files_deleted(synchronizer: SynchronizerLegacy):
    mock_worker = MagicMock()
    synchronizer._queue_processors = [mock_worker]
    files = [Path("media/delete1.txt")]

    synchronizer.collection_files_deleted(files)

    assert mock_worker.put_to_queue.call_count == 1

    call = mock_worker.put_to_queue.call_args[0][0]
    assert isinstance(call.task, SyncTaskDelete)
    assert call.priority == Priority.LOW


# def test_get_stats(synchronizer):
#     mock_sync_queue = MagicMock()
#     mock_sync_queue._connector = "SyncBackend"
#     mock_sync_queue._stats.remaining_files = 5
#     mock_sync_queue._stats.success = 3
#     mock_sync_queue._stats.fail = 1

#     mock_regular_sync = MagicMock()
#     mock_regular_sync._control_connection = "RegularBackend"
#     mock_regular_sync._stats.check_active = True
#     mock_regular_sync._stats.last_check_started = None
#     mock_regular_sync._stats.last_duration = 2.5
#     mock_regular_sync._stats.next_check = None

#     synchronizer._sync_queue = [mock_sync_queue]
#     synchronizer._regular_complete_sync = [mock_regular_sync]

#     stats = synchronizer.get_stats()
#     assert stats.id == "hook-plugin-synchronizer"
#     assert any("Queue:" in sub.name for sub in stats.stats)
#     assert any("Regular Sync:" in sub.name for sub in stats.stats)
