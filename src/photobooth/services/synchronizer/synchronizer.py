import logging
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from ...appconfig import appconfig
from ..base import BaseService
from .connectors import connector_factory
from .share import AbstractMediashare, share_factory
from .sync_regularcomplete import SyncRegularcomplete
from .threadedqueueprocessor import ThreadedQueueProcessor
from .types import Priority, PriorizedTask, SyncTaskDelete, SyncTaskUpload
from .utils import get_remote_filepath

logger = logging.getLogger(__name__)


@dataclass
class SubStats:
    name: str
    val: str | int | float | None
    format: str | None = None


@dataclass
class SubList:
    name: str
    val: list[SubStats]


@dataclass
class GenericStats:
    id: str
    actions: list[str] = field(default_factory=list)
    stats: list[SubStats | SubList] = field(default_factory=list)


class Synchronizer(BaseService):
    def __init__(self):
        super().__init__()

        self._sync_queue: list[ThreadedQueueProcessor] = []
        self._regular_complete_sync: list[SyncRegularcomplete] = []
        self._shares: list[AbstractMediashare] = []

    def start(self):
        super().start()

        self.reset()

        if not appconfig.synchronizer.common.enabled:
            logger.info("Synchronizer Plugin is disabled")
            super().disabled()
            return

        # consumes the queue and uploads/deletes/modifies remote filesystem according to the queue.
        for cfg in appconfig.synchronizer.backends:
            if not cfg.enabled:
                continue

            threadedqueueprocessor = ThreadedQueueProcessor(cfg.backend_config.connector)

            if cfg.enable_share_link:
                share = share_factory(cfg.backend_config, connector_factory.connector_factory(cfg.backend_config.connector))
                share.update_downloadportal()
                self._shares.append(share)

            if cfg.enable_regular_sync:
                self._regular_complete_sync.append(
                    SyncRegularcomplete(
                        connector_factory.connector_factory(cfg.backend_config.connector),
                        threadedqueueprocessor,
                        Path("./media/"),
                    )
                )

            if cfg.enable_immediate_sync:
                self._sync_queue.append(threadedqueueprocessor)

        for instance in self._sync_queue:
            instance.start()

        for instance in self._regular_complete_sync:
            instance.start()

        super().started()

    def stop(self):
        super().stop()

        for instance in self._sync_queue:
            instance.stop()

        for instance in self._regular_complete_sync:
            instance.stop()

        super().stopped()

    def reset(self):
        self._sync_queue = []
        self._regular_complete_sync = []
        self._shares = []

    def _put_to_workers_queues(self, priorized_task: PriorizedTask):
        for sync_queue in self._sync_queue:
            sync_queue.put_to_queue(priorized_task)

    def stats(self) -> dict[str, Any]:
        out = GenericStats(id="tis Plugin ID")

        for sync_queue in self._sync_queue:
            sqs = sync_queue._stats
            out.stats.append(
                SubList(
                    str(sync_queue),
                    [
                        SubStats("remaining", sqs.remaining_files),
                        SubStats("success", sqs.success),
                        SubStats("failed", sqs.fail),
                    ],
                )
            )

        for regular_complete_sync in self._regular_complete_sync:
            rcss = regular_complete_sync._stats

            out.stats.append(
                SubList(
                    str(regular_complete_sync),
                    [
                        SubStats("check_active", rcss.check_active),
                        SubStats("last_check_started", rcss.last_check_started.astimezone().strftime("%X") if rcss.last_check_started else None),
                        SubStats("last_duration", rcss.last_duration),
                        SubStats("next_check", rcss.next_check.astimezone().strftime("%X") if rcss.next_check else None),
                    ],
                )
            )
        out_dict = asdict(out)
        print(out_dict)
        return out_dict

    def get_share_links(self, filepath_local: Path) -> list[str]:
        share_links: list[str] = []

        if not appconfig.synchronizer.common.enable_share_links:
            logger.info("share link generation is disabled globally in synchronizer plugin")
            return []

        for instance in self._shares:
            filepath_remote = get_remote_filepath(filepath_local)
            share_link = instance.get_share_link(filepath_remote)
            if share_link:
                share_links.append(share_link)

        return share_links

    # @hookimpl
    def collection_original_file_added(self, files: list[Path]):
        for file in files:
            self._put_to_workers_queues(PriorizedTask(Priority.LOW, SyncTaskUpload(file, get_remote_filepath(file))))

    # @hookimpl
    def collection_files_added(self, files: list[Path]):
        for file in files:
            self._put_to_workers_queues(PriorizedTask(Priority.HIGH, SyncTaskUpload(file, get_remote_filepath(file))))

    # @hookimpl
    def collection_files_updated(self, files: list[Path]):
        for file in files:
            self._put_to_workers_queues(PriorizedTask(Priority.HIGH, SyncTaskUpload(file, get_remote_filepath(file))))

    # @hookimpl
    def collection_files_deleted(self, files: list[Path]):
        for file in files:
            self._put_to_workers_queues(PriorizedTask(Priority.LOW, SyncTaskDelete(get_remote_filepath(file))))
