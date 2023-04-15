"""
_summary_
"""
import logging
import json
import threading
import platform
import psutil
from pymitter import EventEmitter
from src.repeatedtimer import RepeatedTimer
from src.imageservers import ImageServerAbstract

logger = logging.getLogger(__name__)

STATS_INTERVAL_TIMER = 2  # every x seconds


class InformationService:
    """_summary_"""

    def __init__(self, evtbus: EventEmitter, imageservers: ImageServerAbstract):
        # dependencies
        self._evtbus: EventEmitter = evtbus
        self._imageservers: ImageServerAbstract = imageservers

        # objects
        self._stats_interval_timer: RepeatedTimer = RepeatedTimer(
            STATS_INTERVAL_TIMER, self._on_stats_interval_timer
        )

        # registered events
        self._evtbus.on("publishSSE/initial", self._on_stats_interval_timer)

        logger.info("initialized information service")

    def start(self):
        """_summary_"""
        self._stats_interval_timer.start()

    def stop(self):
        """_summary_"""
        self._stats_interval_timer.stop()

    def _on_stats_interval_timer(self):
        """_summary_"""

        # gather information to be sent off on timer tick:
        cpu1_5_15 = self._gather_cpu1_5_15()
        active_threads = self._gather_active_threads()
        memory = self._gather_memory()
        cma = self._gather_cma()
        disk = self._gather_disk()
        imageservers_stats = self._gather_imageservers_stats()

        self._evtbus.emit(
            "publishSSE",
            sse_event="information",
            sse_data=json.dumps(
                {
                    "cpu1_5_15": cpu1_5_15,
                    "active_threads": active_threads,
                    "memory": memory,
                    "cma": cma,
                    "disk": disk,
                    "imageserver_stats": imageservers_stats,
                }
            ),
        )

    def _gather_cpu1_5_15(self):
        return [round(x / psutil.cpu_count() * 100, 2) for x in psutil.getloadavg()]

    def _gather_active_threads(self):
        return threading.active_count()

    def _gather_memory(self):
        return psutil.virtual_memory()._asdict()

    def _gather_cma(self):
        try:
            meminfo = dict(
                (i.split()[0].rstrip(":"), int(i.split()[1]))
                for i in open("/proc/meminfo", encoding="utf-8").readlines()
            )

            cma = {"CmaTotal": meminfo["CmaTotal"], "CmaFree": meminfo["CmaFree"]}
        except FileNotFoundError:
            # linux only
            cma = {"CmaTotal": None, "CmaFree": None}

        return cma

    def _gather_disk(self):
        if platform.system() == "Linux":
            disk = psutil.disk_usage("/")._asdict()
        elif platform.system() == "Windows":
            disk = psutil.disk_usage("C:")._asdict()
        else:
            raise RuntimeError("platform not supported")

        return disk

    def _gather_imageservers_stats(self):
        return self._imageservers.stats()
