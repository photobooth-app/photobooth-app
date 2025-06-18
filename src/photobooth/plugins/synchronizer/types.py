from queue import Queue

from .models import SyncTaskDelete, SyncTaskUpload

taskSyncType = SyncTaskUpload | SyncTaskDelete | None
queueSyncType = Queue[taskSyncType]
