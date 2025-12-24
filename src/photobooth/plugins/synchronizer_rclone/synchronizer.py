import logging
from pathlib import Path

from ...models.genericstats import GenericStats
from .. import hookimpl
from ..base_plugin import BasePlugin
from .config import SynchronizerConfig
from .sync_full import SyncFull
from .sync_queue import SyncQueue
from .types import Priority, PriorizedTask, SyncTaskDelete, SyncTaskUpload
from .utils import get_corresponding_remote_file, get_corresponding_remote_folder

logger = logging.getLogger(__name__)


class Synchronizer(BasePlugin[SynchronizerConfig]):
    def __init__(self):
        super().__init__()

        self._config = SynchronizerConfig()
        self.__sync_queue: list[SyncQueue] = []
        self.__sync_full: list[SyncFull] = []
        # self.__shares: list[Shares] = []

    @hookimpl
    def start(self):
        self.reset()

        if not self._config.common.enabled:
            logger.info("Synchronizer Plugin is disabled")
            return

        # consumes the queue and uploads/deletes/modifies remote filesystem according to the queue.
        for cfgGrp in self._config.remotes:
            if not cfgGrp.enabled:
                continue

            if cfgGrp.syncfullconfig.enable_regular_sync:
                sync_full = SyncFull(Path("./media/"), cfgGrp.syncfullconfig, cfgGrp.rcloneRemoteConfig)
                self.__sync_full.append(sync_full)

            if cfgGrp.syncqueueconfig.enable_immediate_sync:
                queueprocessor = SyncQueue(cfgGrp.syncqueueconfig, cfgGrp.rcloneRemoteConfig)
                self.__sync_queue.append(queueprocessor)

        for instance in self.__sync_queue:
            instance.start()

        for instance in self.__sync_full:
            instance.start()

    @hookimpl
    def stop(self):
        for instance in self.__sync_queue:
            instance.stop()

        for instance in self.__sync_full:
            instance.stop()

    def reset(self):
        self.__sync_queue = []
        self.__sync_full = []
        self._shares = []

    def _put_to_processors_queues(self, priorized_task: PriorizedTask):
        for queue_processor in self.__sync_queue:
            queue_processor.put_to_queue(priorized_task)

    @hookimpl
    def get_stats(self) -> GenericStats | None:
        if self._config.common.enabled is False:
            # avoids display of an empty stats object in the admin dashboard
            return None

        out = GenericStats(id="hook-plugin-synchronizer", name="Synchronizer")

        # for queue_processor in self.__sync_queue:
        #     sqs = queue_processor.__stats
        #     out.stats.append(
        #         SubList(
        #             name=str(queue_processor),
        #             val=[
        #                 SubStats("remaining", sqs.remaining_files),
        #                 SubStats("success", sqs.success),
        #                 SubStats("failed", sqs.fail),
        #             ],
        #         )
        #     )

        # for regular_complete_sync in self.__sync_full:
        #     rcss = regular_complete_sync._stats

        #     out.stats.append(
        #         SubList(
        #             name=str(regular_complete_sync),
        #             val=[
        #                 SubStats("check_active", rcss.check_active, display=DisplayEnum.spinner),
        #                 SubStats("last_check_started", rcss.last_check_started.astimezone().strftime("%X") if rcss.last_check_started else None),
        #                 SubStats("last_duration", rcss.last_duration, unit="s"),
        #                 SubStats("next_check", rcss.next_check.astimezone().strftime("%X") if rcss.next_check else None),
        #                 SubStats("files_queued_last_check", rcss.files_queued_last_check),
        #             ],
        #         )
        #     )

        return out

    @hookimpl
    def get_share_links(self, filepath_local: Path) -> list[str]:
        share_links: list[str] = []

        if not self._config.common.enable_share_links:
            logger.info("share link generation is disabled globally in synchronizer plugin")
            return []

        for instance in self._shares:
            filepath_remote = get_corresponding_remote_file(filepath_local)
            share_link = instance.get_share_link(filepath_remote)
            if share_link:
                share_links.append(share_link)

        return share_links

    @hookimpl
    def collection_original_file_added(self, files: list[Path]):
        for file in files:
            self._put_to_processors_queues(PriorizedTask(Priority.LOW, SyncTaskUpload(file, get_corresponding_remote_folder(file))))

    @hookimpl
    def collection_files_added(self, files: list[Path]):
        for file in files:
            self._put_to_processors_queues(PriorizedTask(Priority.HIGH, SyncTaskUpload(file, get_corresponding_remote_folder(file))))

    @hookimpl
    def collection_files_updated(self, files: list[Path]):
        for file in files:
            self._put_to_processors_queues(PriorizedTask(Priority.HIGH, SyncTaskUpload(file, get_corresponding_remote_folder(file))))

    @hookimpl
    def collection_files_deleted(self, files: list[Path]):
        for file in files:
            self._put_to_processors_queues(PriorizedTask(Priority.LOW, SyncTaskDelete(get_corresponding_remote_file(file))))
