import platform
import socket
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import psutil
from psutil._common import sbattery
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ..__version__ import __version__
from ..database.database import engine
from ..database.models import ShareLimits, UsageStats
from ..database.schemas import ShareLimitsPublic, UsageStatsPublic
from ..utils.repeatedtimer import RepeatedTimer
from .aquisition import AquisitionService
from .base import BaseService
from .sse import SseEventIntervalInformationRecord, SseEventOnetimeInformationRecord, SseService

STATS_INTERVAL_TIMER = 2  # every x seconds


class InformationService(BaseService):
    """_summary_"""

    def __init__(self, sse_service: SseService, aquisition_service: AquisitionService):
        super().__init__(sse_service)

        self._aquisition_service = aquisition_service

        # objects
        self._stats_interval_timer: RepeatedTimer = RepeatedTimer(STATS_INTERVAL_TIMER, self._on_stats_interval_timer)

        # log some very basic common information
        self._logger.info(f"{platform.system()=}")
        self._logger.info(f"{platform.uname()=}")
        self._logger.info(f"{platform.release()=}")
        self._logger.info(f"{platform.machine()=}")
        self._logger.info(f"{platform.python_version()=}")
        self._logger.info(f"{platform.node()=}")
        self._logger.info(f"{self._gather_model()=}")
        self._logger.info(f"{psutil.cpu_count()=}")
        self._logger.info(f"{psutil.cpu_count(logical=False)=}")
        self._logger.info(f"{psutil.disk_partitions()=}")
        self._logger.info(f"{psutil.disk_usage(str(Path.cwd().absolute()))=}")
        self._logger.info(
            [(name, [addr.address for addr in addrs if addr.family == socket.AF_INET]) for name, addrs in psutil.net_if_addrs().items()]
        )
        self._logger.info(f"{psutil.virtual_memory()=}")
        # run python with -O (optimized) sets debug to false and disables asserts from bytecode
        self._logger.info(f"{__debug__=}")

        self._logger.info("initialized information service")

    def start(self):
        super().start()
        self._stats_interval_timer.start()
        super().started()

    def stop(self):
        super().stop()
        self._stats_interval_timer.stop()
        super().stopped()

    def stats_counter_reset(self, field: str):
        try:
            with Session(engine) as session:
                statement = delete(UsageStats).where(UsageStats.action == field)
                result = session.execute(statement)
                session.commit()

                self._logger.info(f"deleted {result.rowcount} entries from UsageStats")

        except Exception as exc:
            raise RuntimeError(f"failed to reset {field}, error: {exc}") from exc

    def stats_counter_reset_all(self):
        try:
            with Session(engine) as session:
                statement = delete(UsageStats)
                results = session.execute(statement)
                session.commit()
                self._logger.info(f"deleted {results.rowcount} entries from UsageStats")

        except Exception as exc:
            raise RuntimeError(f"failed to reset statscounter, error: {exc}") from exc

    def stats_counter_increment(self, field):
        try:
            with Session(engine) as session:
                db_field_entry = session.get(UsageStats, field)
                if not db_field_entry:
                    # add 0 to db
                    session.add(UsageStats(action=field))

                statement = select(UsageStats).where(UsageStats.action == field)
                result = session.scalars(statement).one()
                result.count += 1
                result.last_used_at = datetime.now().astimezone()
                session.add(result)
                session.commit()
        except Exception as exc:
            raise RuntimeError(f"failed to update statscounter, error: {exc}") from exc

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
                model=self._gather_model(),
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
                memory=self._gather_memory(),
                cma=self._gather_cma(),
                backends=self._gather_backends_stats(),
                stats_counter=self._gather_stats_counter(),
                limits_counter=self._gather_limits_counter(),
                battery_percent=self._gather_battery(),
                temperatures=self._gather_temperatures(),
            ),
        )

    def _gather_limits_counter(self) -> list[ShareLimitsPublic]:
        with Session(engine) as session:
            statement = select(ShareLimits)
            results = session.scalars(statement).all()
            # https://stackoverflow.com/questions/77637278/sqlalchemy-model-to-json
            return [ShareLimitsPublic.model_validate(result).model_dump(mode="json") for result in results]

    def _gather_stats_counter(self) -> list[UsageStatsPublic]:
        with Session(engine) as session:
            statement = select(UsageStats)
            results = session.scalars(statement).all()
            # https://stackoverflow.com/questions/77637278/sqlalchemy-model-to-json
            return [UsageStatsPublic.model_validate(result).model_dump(mode="json") for result in results]

    def _gather_cpu1_5_15(self):
        return [round(x / psutil.cpu_count() * 100, 2) for x in psutil.getloadavg()]

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

    def _gather_backends_stats(self):
        return self._aquisition_service.stats()

    def _gather_disk(self):
        return psutil.disk_usage(str(Path.cwd().absolute()))._asdict()

    def _gather_model(self) -> str:
        model = "unknown"

        if platform.system() == "Linux":
            # try to get raspberry model
            try:
                with open("/proc/device-tree/model") as f:
                    model = f.read()
            except Exception:
                self._logger.info("cannot detect computer model")

        return model

    def _gather_battery(self) -> int:
        battery_percent = None

        # https://psutil.readthedocs.io/en/latest/index.html#psutil.sensors_battery
        # None if not determinable otherwise named tuple.
        # clamp to 0...100%
        battery: sbattery | None = psutil.sensors_battery() if hasattr(psutil, "sensors_battery") else None
        if battery:
            battery_percent = max(min(100, round(battery.percent, None)), 0)

        return battery_percent

    def _gather_temperatures(self) -> dict[str, Any]:
        temperatures = {}

        # https://psutil.readthedocs.io/en/latest/index.html#psutil.sensors_temperatures
        psutil_temperatures = psutil.sensors_temperatures() if hasattr(psutil, "sensors_temperatures") else {}
        for name, entry in psutil_temperatures.items():
            temperatures[name] = round(entry[0].current, 1)  # there could be multiple sensors to one zone, we just use the first.

        return temperatures
