from queue import PriorityQueue

from .models import SyncTaskDelete, SyncTaskUpload

priorityTaskSyncType = tuple[int, int, SyncTaskUpload | SyncTaskDelete | None]
priorityQueueSyncType = PriorityQueue[priorityTaskSyncType]
