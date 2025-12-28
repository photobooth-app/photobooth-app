import logging
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from photobooth.plugins.synchronizer_legacy.config import FilesystemConnectorConfig
from photobooth.plugins.synchronizer_legacy.queueprocessor import QueueProcessor
from photobooth.plugins.synchronizer_legacy.types import Priority, PriorizedTask, SyncTaskDelete, SyncTaskUpload

logger = logging.getLogger(name=None)


@pytest.fixture
def mock_connector():
    mock = MagicMock()
    return mock


@pytest.fixture
def queue_processor(tmp_path: Path):
    # setup
    qp = QueueProcessor(FilesystemConnectorConfig(target_dir=tmp_path))

    yield qp

    if qp.is_started():
        qp.stop()


def test_upload_delete(queue_processor: QueueProcessor, tmp_path: Path):
    priorized_task = PriorizedTask(priority=Priority.HIGH, task=SyncTaskUpload(Path("src/tests/assets/input.jpg"), Path("./input.jpg")))

    ## UPLOAD NORMAL

    # it's okay to queue items before the processor has been started...
    queue_processor.put_to_queue(priorized_task)
    assert queue_processor._stats.remaining_files == 1

    queue_processor.start()

    # wait until finished, use task_done and join in future.
    queue_processor._queue.join()

    assert queue_processor._stats.success == 1
    assert queue_processor._stats.fail == 0
    assert queue_processor._stats.remaining_files == 0
    assert queue_processor._connector.do_check_issame(Path("src/tests/assets/input.jpg"), Path("./input.jpg"))  # ensure file exists in remote

    ## UPLOAD FAILS

    with patch.object(queue_processor._connector, "do_upload", side_effect=Exception("upload failed")):
        queue_processor.put_to_queue(priorized_task)

        queue_processor._queue.join()

        assert queue_processor._stats.success == 1
        assert queue_processor._stats.fail == 1
        assert queue_processor._stats.remaining_files == 0

    ## DELETE FROM REMOTE
    priorized_task = PriorizedTask(priority=Priority.HIGH, task=SyncTaskDelete(Path("./input.jpg")))

    queue_processor.put_to_queue(priorized_task)

    # wait until finished, use task_done and join in future.
    queue_processor._queue.join()

    assert queue_processor._stats.success == 2
    assert queue_processor._stats.fail == 1
    assert queue_processor._stats.remaining_files == 0
    assert not Path(tmp_path, "./input.jpg").exists()  # ensure doesn't exist after delete


def test_put_queue_stopped_already(queue_processor: QueueProcessor):
    priorized_task = PriorizedTask(priority=Priority.HIGH, task=SyncTaskUpload(Path("src/tests/assets/input.jpg"), Path("./input.jpg")))

    queue_processor.start()
    queue_processor.stop()

    queue_processor.put_to_queue(priorized_task)

    assert queue_processor._stats.success == 0
    assert queue_processor._stats.fail == 0
    assert queue_processor._stats.remaining_files == 0
