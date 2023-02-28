import logging
import json
import threading
import platform
import psutil
from pymitter import EventEmitter
from src.repeatedtimer import RepeatedTimer

logger = logging.getLogger(__name__)


class InformationService:
    def __init__(self, evtbus: EventEmitter):
        self._evtbus: EventEmitter = evtbus

        self._rt = RepeatedTimer(10, self._on_timer)

        self._evtbus.on("publishSSE/initial", self._on_timer)

        logger.info("initialized information service")

    def stop(self):
        self._rt.stop()

    def _on_timer(self):
        cpu1_5_15 = [
            round(x / psutil.cpu_count() * 100, 2) for x in psutil.getloadavg()
        ]
        memory = psutil.virtual_memory()._asdict()

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
                    "disk": disk,
                }
            ),
        )
