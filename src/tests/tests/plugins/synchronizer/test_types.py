import logging
from pathlib import Path

from photobooth.plugins.synchronizer_legacy.types import Priority, PriorizedTask, SyncTaskDelete, SyncTaskUpload

logger = logging.getLogger(name=None)


def test_get_str():
    syncTaskUpload = SyncTaskUpload(Path("local"), Path("remote"))
    assert syncTaskUpload.__str__()
    assert SyncTaskDelete(Path("remote")).__str__()
    assert PriorizedTask(Priority.HIGH, syncTaskUpload).__str__()
