import logging
import subprocess
from datetime import datetime

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ..appconfig import appconfig
from ..database.database import engine
from ..database.models import Mediaitem, ShareLimits
from .base import BaseService
from .sse import sse_service
from .sse.sse_ import SseEventFrontendNotification

logger = logging.getLogger(__name__)
TIMEOUT_PROCESS_RUN = 6  # command to print needs to complete within 6 seconds.


class ShareService(BaseService):
    def __init__(self):
        super().__init__()

        # common objects
        pass

        # custom service objects
        pass

    def start(self):
        super().start()
        pass
        super().started()

    def stop(self):
        super().stop()
        pass
        super().stopped()

    def share(self, mediaitem: Mediaitem, config_index: int = 0, parameters: dict[str, str] | None = None):
        """print mediaitem"""

        if not appconfig.share.sharing_enabled:
            sse_service.dispatch_event(
                SseEventFrontendNotification(
                    color="negative",
                    message="Share service is disabled! Enable in config first.",
                    caption="Share Service Error",
                )
            )
            raise ConnectionRefusedError("Share service is disabled! Enable in config first.")

        # get config
        try:
            action_config = appconfig.share.actions[config_index]
        except Exception as exc:
            logger.critical(f"could not find action configuration with index {config_index}, error {exc}")
            raise exc

        # check counter limit

        with Session(engine) as session:
            statement = select(ShareLimits).where(ShareLimits.action == action_config.name)
            results = session.scalars(statement)
            result = results.one_or_none()

        current_shares = result.count if result else 0
        last_used_at = result.last_used_at if result else None

        if self.is_quota_exceeded(current_shares, action_config.processing.max_shares):
            sse_service.dispatch_event(
                SseEventFrontendNotification(
                    color="negative",
                    message=f"{action_config.trigger.ui_trigger.title} quota exceeded ({action_config.processing.max_shares} maximum)",
                    caption="Share/Print quota",
                )
            )
            raise BlockingIOError("Maximum number of Share/Print reached!")

        # block queue new prints until configured time is over
        remaining_s = self.remaining_time_blocked(action_config.processing.share_blocked_time, last_used_at)
        if remaining_s > 0:
            sse_service.dispatch_event(
                SseEventFrontendNotification(
                    color="info",
                    message=f"Request ignored! Wait {remaining_s:.0f}s before trying again.",
                    caption="Share Service Error",
                )
            )
            raise BlockingIOError(f"Request ignored! Wait {remaining_s:.0f}s before trying again.")

        # filename absolute to print, use in printing command
        filename = mediaitem.processed.absolute()

        # print command
        logger.info(f"share/print {filename=}")

        if parameters is None:
            share_parameters = {parameter.key: parameter.default for parameter in action_config.processing.parameters}
            logger.info(f"no share parameters given by user, continue using the defaults: {share_parameters}")
        else:
            share_parameters = parameters
            logger.info(f"share parameters given by user: {share_parameters}")

        share_parameters.pop("filename", None)  # if filename is configured by user, remove it, because the app sets it.

        try:
            formatted_command = str(action_config.processing.share_command).format(filename=filename, **share_parameters)
        except KeyError as exc:
            raise RuntimeError(f"Error in configuration! Parameter {exc} is defined in command but was not configured as parameter!") from exc
        except TypeError as exc:
            # usually this error is prevented by having the pattern= in the pydantic field in config already.
            raise RuntimeError(f"Error in configuration! Probably illegal parameter name defined, error: {exc}") from exc

        sse_service.dispatch_event(
            SseEventFrontendNotification(
                color="positive",
                message=f"Process '{action_config.name}' started.",
                caption="Share Service",
                spinner=True,
            )
        )
        try:
            completed_process = subprocess.run(
                formatted_command,
                capture_output=True,
                check=True,
                timeout=TIMEOUT_PROCESS_RUN,
                shell=True,  # needs to be shell so a string as command is accepted.
            )

        except Exception as exc:
            sse_service.dispatch_event(SseEventFrontendNotification(color="negative", message=f"{exc}", caption="Share/Print Error"))
            raise RuntimeError(f"Process failed, error {exc}") from exc
        else:
            logger.info(f"cmd={completed_process.args}")
            logger.info(f"stdout={completed_process.stdout}")
            logger.debug(f"stderr={completed_process.stderr}")

            logger.info(f"command started successfully {mediaitem}")

        updated_current_shares = self.limit_counter_increment(action_config.name)

        if action_config.processing.max_shares > 0:
            # quota is enabled.

            sse_service.dispatch_event(
                SseEventFrontendNotification(
                    color="info",
                    message=f"{action_config.trigger.ui_trigger.title} quota is {updated_current_shares} of {action_config.processing.max_shares}",
                    caption="Share/Print quota",
                )
            )

    def limit_counter_reset(self, field: str):
        try:
            with Session(engine) as session:
                statement = delete(ShareLimits).where(ShareLimits.action == field)
                result = session.execute(statement)
                session.commit()

                logger.info(f"deleted {result.rowcount} items from ShareLimits")

        except Exception as exc:
            raise RuntimeError(f"failed to reset {field}, error: {exc}") from exc

    def limit_counter_reset_all(self):
        try:
            with Session(engine) as session:
                statement = delete(ShareLimits)
                results = session.execute(statement)
                session.commit()
                logger.info(f"deleted {results.rowcount} entries from ShareLimits")

        except Exception as exc:
            raise RuntimeError(f"failed to reset ShareLimits, error: {exc}") from exc

    def limit_counter_increment(self, field: str) -> int:
        try:
            with Session(engine) as session:
                db_entry = session.get(ShareLimits, field)
                if not db_entry:
                    # add 0 to db
                    session.add(ShareLimits(action=field))

                statement = select(ShareLimits).where(ShareLimits.action == field)
                results = session.scalars(statement)
                result = results.one()
                result.count += 1
                result.last_used_at = datetime.now()
                session.add(result)
                session.commit()

                return result.count
        except Exception as exc:
            raise RuntimeError(f"failed to update ShareLimits, error: {exc}") from exc

    def is_quota_exceeded(self, current_shares: int, max_shares: int) -> bool:
        if max_shares > 0 and current_shares >= max_shares:
            return True
        else:
            return False

    def remaining_time_blocked(self, shall_block_time_s: int, last_used_at: datetime | None) -> float:
        if last_used_at is None:
            return 0.0

        delta = (datetime.now() - last_used_at).total_seconds()

        if delta >= shall_block_time_s:
            # last print is longer than configured time in the past - return 0 to indicate no wait time
            return 0.0
        else:
            # there is some time to wait left.
            return shall_block_time_s - delta

    def _print_timer_fun(self):
        ## thread to send updates to client about remaining blocked time
        pass
