"""
_summary_
"""

import platform
import socket
import sys
import threading
from pathlib import Path

import psutil

from ..__version__ import __version__
from ..utils.repeatedtimer import RepeatedTimer
from .aquisitionservice import AquisitionService
from .baseservice import BaseService
from .printingservice import PrintingService
from .sseservice import SseEventIntervalInformationRecord, SseEventOnetimeInformationRecord, SseService

STATS_INTERVAL_TIMER = 2  # every x seconds


class InformationService(BaseService):
    """_summary_"""

    def __init__(self, sse_service: SseService, aquisition_service: AquisitionService, printing_service: PrintingService):
        super().__init__(sse_service)

        self._aquisition_service = aquisition_service
        self._printing_service = printing_service

        # objects
        self._stats_interval_timer: RepeatedTimer = RepeatedTimer(STATS_INTERVAL_TIMER, self._on_stats_interval_timer)

        # log some very basic common information
        self._logger.info(f"{platform.system()=}")
        self._logger.info(f"{platform.uname()=}")
        self._logger.info(f"{platform.release()=}")
        self._logger.info(f"{platform.machine()=}")
        self._logger.info(f"{platform.python_version()=}")
        self._logger.info(f"{platform.node()=}")
        self._logger.info(f"{psutil.cpu_count()=}")
        self._logger.info(f"{psutil.cpu_count(logical=False)=}")
        self._logger.info(f"{psutil.disk_partitions()=}")
        if platform.system() in ["Linux", "Darwin"]:
            self._logger.info(f"{psutil.disk_usage('/')=}")
        elif platform.system() == "Windows":
            self._logger.info(f"{psutil.disk_usage('C:')=}")
        self._logger.info(
            [
                (
                    name,
                    [addr.address for addr in addrs if addr.family == socket.AF_INET],
                )
                for name, addrs in psutil.net_if_addrs().items()
            ]
        )
        self._logger.info(f"{psutil.virtual_memory()=}")
        # run python with -O (optimized) sets debug to false and disables asserts from bytecode
        self._logger.info(f"{__debug__=}")

        self._logger.info("initialized information service")

    def start(self):
        """_summary_"""
        self._stats_interval_timer.start()

    def stop(self):
        """_summary_"""
        self._stats_interval_timer.stop()

    def initial_emit(self):
        """_summary_"""

        # gather one time on connect information to be sent off:
        self._sse_service.dispatch_event(
            SseEventOnetimeInformationRecord(
                version=__version__,
                platform_system=platform.system(),
                platform_release=platform.release(),
                platform_machine=platform.machine(),
                platform_python_version=platform.python_version(),
                platform_node=platform.node(),
                platform_cpu_count=psutil.cpu_count(),
                data_directory=Path.cwd().resolve(),
                python_executable=sys.executable,
                disk=self._gather_disk(),
            ),
        )

        # also send interval data initially once
        self._on_stats_interval_timer()

    def _on_stats_interval_timer(self):
        """_summary_"""

        # gather information to be sent off on timer tick:
        self._sse_service.dispatch_event(
            SseEventIntervalInformationRecord(
                cpu1_5_15=self._gather_cpu1_5_15(),
                active_threads=self._gather_active_threads(),
                memory=self._gather_memory(),
                cma=self._gather_cma(),
                backends=self._gather_backends_stats(),
                printer=self._gather_printing_stats(),
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
            with open("/proc/meminfo", encoding="utf-8") as file:
                meminfo = dict((i.split()[0].rstrip(":"), int(i.split()[1])) for i in file.readlines())

            cma = {
                "CmaTotal": meminfo.get("CmaTotal", None),
                "CmaFree": meminfo.get("CmaFree", None),
            }
        except FileNotFoundError:
            # linux only
            cma = {"CmaTotal": None, "CmaFree": None}

        return cma

    def _gather_printing_stats(self):
        return self._printing_service.stats()

    def _gather_backends_stats(self):
        return self._aquisition_service.stats()

    def _gather_disk(self):
        if platform.system() in ["Linux", "Darwin"]:
            disk = psutil.disk_usage("/")._asdict()
        elif platform.system() == "Windows":
            disk = psutil.disk_usage("C:")._asdict()
        else:
            raise RuntimeError("platform not supported")

        return disk
