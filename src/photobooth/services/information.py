import logging
import platform
import subprocess
import sys
from datetime import datetime
from importlib.metadata import version
from pathlib import Path
from typing import Any, cast

import psutil
from psutil._common import sbattery
from sqlalchemy import CursorResult, delete, func, select
from sqlalchemy.orm import Session

from .. import CACHE_PATH, MEDIA_PATH, RECYCLE_PATH, TMP_PATH
from ..database.database import engine
from ..database.models import Cacheditem, Mediaitem, ShareLimits, UsageStats
from ..database.schemas import ShareLimitsPublic, UsageStatsPublic
from ..models.genericstats import GenericStats
from ..plugins import pm as pluggy_pm
from ..utils.repeatedtimer import RepeatedTimer
from ..utils.stoppablethread import StoppableThread
from .acquisition import AcquisitionService
from .base import BaseService
from .sse import sse_service
from .sse.sse_ import SseEventIntervalInformationRecord, SseEventOnetimeInformationRecord

logger = logging.getLogger(__name__)
STATS_INTERVAL_TIMER = 2  # every x seconds


class InformationService(BaseService):
    def __init__(self, acquisition_service: AcquisitionService):
        super().__init__()

        self._acquisition_service = acquisition_service

        # objects
        self._stats_interval_timer: RepeatedTimer = RepeatedTimer(STATS_INTERVAL_TIMER, self._on_stats_interval_timer)
        self._cpu_percent_thread = StoppableThread(name="_on_cpu_percent_worker", target=self._on_cpu_percent_fun, daemon=True)
        self._cpu_percent: float = 0.0
        self._skip_gathering: set = set()

        # log some very basic common information
        logger.info(f"Platform: {platform.uname()}")
        logger.info(f"System release: {platform.release()}")
        logger.info(f"Machine: {platform.machine()}")
        logger.info(f"Python version: {platform.python_version()}")
        logger.info(f"Computer model: {self._gather_model()}")
        logger.info(f"CPU count: {psutil.cpu_count()}")
        logger.info(f"Disk usage of working dir: {psutil.disk_usage(str(Path.cwd().absolute())).percent}")

    def start(self):
        super().start()
        self._stats_interval_timer.start()
        self._cpu_percent_thread = StoppableThread(name="_on_cpu_percent_worker", target=self._on_cpu_percent_fun, daemon=True)
        self._cpu_percent_thread.start()
        super().started()

    def stop(self):
        super().stop()
        self._stats_interval_timer.stop()
        self._cpu_percent_thread.stop()
        super().stopped()

    def stats_counter_reset(self, field: str):
        try:
            with Session(engine) as session:
                statement = delete(UsageStats).where(UsageStats.action == field)
                result = cast(CursorResult, session.execute(statement))
                session.commit()

                logger.info(f"deleted {result.rowcount} entries from UsageStats")

        except Exception as exc:
            raise RuntimeError(f"failed to reset {field}, error: {exc}") from exc

    def stats_counter_reset_all(self):
        try:
            with Session(engine) as session:
                statement = delete(UsageStats)
                result = cast(CursorResult, session.execute(statement))
                session.commit()
                logger.info(f"deleted {result.rowcount} entries from UsageStats")

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

    def get_initial_inforecord(self):
        return SseEventOnetimeInformationRecord(
            version=version("photobooth-app"),
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
        )

    def get_interval_inforecord(self):
        return SseEventIntervalInformationRecord(
            cpu_percent=self._gather_cpu_percent(),
            memory=self._gather_memory(),
            cma=self._gather_cma(),
            backends=self._gather_backends_stats(),
            stats_counter=self._gather_stats_counter(),
            limits_counter=self._gather_limits_counter(),
            battery_percent=self._gather_battery(),
            temperatures=self._gather_temperatures(),
            mediacollection=self._gather_mediacollection(),
            plugins=self._gather_plugins(),
            pi_throttled_flags=self._gather_pi_throttled_flags(),
        )

    def initial_emit(self):
        # gather one time on connect information to be sent off:
        sse_service.dispatch_event(self.get_initial_inforecord())

        # also send interval data initially once
        self._on_stats_interval_timer()

    def _on_stats_interval_timer(self):
        # gather information to be sent off on timer tick:
        sse_service.dispatch_event(self.get_interval_inforecord())

    def _gather_limits_counter(self) -> list[ShareLimitsPublic]:
        with Session(engine) as session:
            statement = select(ShareLimits)
            results = session.scalars(statement).all()
            # https://stackoverflow.com/questions/77637278/sqlalchemy-model-to-json
            return [ShareLimitsPublic.model_validate(result) for result in results]

    def _gather_stats_counter(self) -> list[UsageStatsPublic]:
        with Session(engine) as session:
            statement = select(UsageStats)
            results = session.scalars(statement).all()
            # https://stackoverflow.com/questions/77637278/sqlalchemy-model-to-json
            return [UsageStatsPublic.model_validate(result) for result in results]

    def _gather_mediacollection(self) -> dict[str, Any]:
        out = {}
        with Session(engine) as session:
            statement = select(func.count(Mediaitem.id))
            out["db_mediaitems"] = session.scalars(statement).one()

            statement = select(func.count(Cacheditem.id))
            out["db_cacheditems"] = session.scalars(statement).one()

            out["files_media"] = len(list(Path(f"{MEDIA_PATH}").glob("**/*.*")))  ## recursive match of all files with suffix
            out["files_cache"] = len(list(Path(f"{CACHE_PATH}").glob("**/*.*")))
            out["files_tmp"] = len(list(Path(f"{TMP_PATH}").glob("**/*.*")))

            out["files_recycle"] = len(list(Path(f"{RECYCLE_PATH}").glob("**/*.*")))

        return out

    def _on_cpu_percent_fun(self):
        while not self._cpu_percent_thread.stopped():
            self._cpu_percent = psutil.cpu_percent(interval=2)

    def _gather_cpu_percent(self) -> float:
        return self._cpu_percent

    def _gather_memory(self):
        return psutil.virtual_memory()._asdict()

    def _gather_cma(self) -> dict[str, int | None] | dict[str, None]:
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
        return self._acquisition_service.stats()

    def _gather_disk(self) -> dict[str, int | float]:
        return psutil.disk_usage(str(Path.cwd().absolute()))._asdict()

    def _gather_model(self) -> str:
        model = "unknown"

        if platform.system() == "Linux":
            # try to get raspberry model
            try:
                with open("/proc/device-tree/model") as f:
                    model = f.read().strip("\x00\n")  # strip nulls and newlines
            except Exception:
                pass

        return model

    def _gather_battery(self) -> int | None:
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
        try:
            psutil_temperatures = psutil.sensors_temperatures()  # type: ignore
        except AttributeError:
            # ignore, not supported on win
            pass
        else:
            for name, entry in psutil_temperatures.items():
                temperatures[name] = round(entry[0].current, 1)  # there could be multiple sensors to one zone, we just use the first.

        return temperatures

    def _gather_plugins(self) -> list[GenericStats]:
        return [stat for stat in pluggy_pm.hook.get_stats() if stat is not None]

    def _gather_pi_throttled_flags(self) -> dict[str, bool]:
        """Raspberry Pi system health monitor using vcgencmd.
        Decode throttled bitmask into human-readable flags."""
        flags = {}

        if "pi_throttled_flags" in self._skip_gathering:
            # if vcgencmd failed once, we skip in future because the computer is probably no Pi
            return flags

        try:
            out = subprocess.check_output(["vcgencmd", "get_throttled"]).decode().strip()
            mask = int(out.split("=")[1], 16)

            flags = {
                "undervoltage_now": bool(mask & 0x1),
                "freq_capped_now": bool(mask & 0x2),
                "throttled_now": bool(mask & 0x4),
                "soft_temp_limit_now": bool(mask & 0x8),
                "undervoltage_occurred": bool(mask & 0x10000),
                "freq_capped_occurred": bool(mask & 0x20000),
                "throttled_occurred": bool(mask & 0x40000),
                "soft_temp_limit_occurred": bool(mask & 0x80000),
            }

        except Exception:
            self._skip_gathering.add("pi_throttled_flags")

        return flags
