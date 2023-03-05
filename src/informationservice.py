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

logger = logging.getLogger(__name__)

STATS_INTERVAL_TIMER = 2  # every x seconds


class InformationService:
    """_summary_"""

    def __init__(self, evtbus: EventEmitter):
        self._evtbus: EventEmitter = evtbus

        self._rt = RepeatedTimer(STATS_INTERVAL_TIMER, self._on_timer)

        self._evtbus.on("publishSSE/initial", self._on_timer)

        logger.info("initialized information service")

    def stop(self):
        """_summary_"""
        self._rt.stop()

    def _on_timer(self):
        """_summary_"""
        cpu1_5_15 = [
            round(x / psutil.cpu_count() * 100, 2) for x in psutil.getloadavg()
        ]
        memory = psutil.virtual_memory()._asdict()

        try:
            meminfo = dict(
                (i.split()[0].rstrip(":"), int(i.split()[1]))
                for i in open("/proc/meminfo", encoding="utf-8").readlines()
            )

            cma = {"CmaTotal": meminfo["CmaTotal"], "CmaFree": meminfo["CmaFree"]}
        except FileNotFoundError:
            # linux only
            cma = {"CmaTotal": None, "CmaFree": None}

        if platform.system() == "Linux":
            disk = psutil.disk_usage("/")._asdict()
        elif platform.system() == "Windows":
            disk = psutil.disk_usage("C:")._asdict()

        self._evtbus.emit(
            "publishSSE",
            sse_event="information",
            sse_data=json.dumps(
                {
                    "cpu1_5_15": cpu1_5_15,
                    "active_threads": threading.active_count(),
                    "memory": memory,
                    "cma": cma,
                    "disk": disk,
                }
            ),
        )
