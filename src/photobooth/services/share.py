import logging
import shlex
import subprocess
from datetime import datetime
from typing import cast

from sqlalchemy import CursorResult, delete, select
from sqlalchemy.orm import Session

from ..appconfig import appconfig
from ..database.database import engine
from ..database.models import Mediaitem, ShareLimits
from ..utils.exceptions import ShareCommandError, ShareParameterError, WrongMediaTypeError
from ..utils.printer import PrinterStatus, get_printer_status
from .base import BaseService
from .sse import sse_service
from .sse.sse_ import SseEventTranslateableFrontendNotification

logger = logging.getLogger(__name__)
TIMEOUT_PROCESS_RUN = 6  # command to print needs to complete within 6 seconds.
MAX_SHARE_INPUT_LENGTH = 4096


class ShareService(BaseService):
    def __init__(self):
        super().__init__()

    def start(self):
        super().start()
        super().started()

    def stop(self):
        super().stop()
        super().stopped()

    def share(self, mediaitem: Mediaitem, config_index: int = 0, parameters: dict[str, str] | None = None):
        """print mediaitem"""

        if not appconfig.share.sharing_enabled:
            sse_service.dispatch_event(SseEventTranslateableFrontendNotification(color="negative", message_key="share.service_disabled"))
            raise ConnectionRefusedError("The shareservice is disabled! Please enable it in the admin configuration before use.")

        # get config
        try:
            action_config = appconfig.share.actions[config_index]
        except Exception as exc:
            logger.critical(f"could not find action configuration with index {config_index}, error {exc}")
            raise exc

        # check for handlesOnlyImages and abort if media_type is not an image
        if action_config.handles_images_only and mediaitem.media_type not in ("image", "collage"):
            # this action handles images only, so ensure it is an image, otherwise send SSE notification.
            sse_service.dispatch_event(
                SseEventTranslateableFrontendNotification(
                    color="negative",
                    message_key="share.wrong_media_type",
                    context_data={"action_name": action_config.name},
                )
            )
            raise WrongMediaTypeError(f"The action can handle only images but {mediaitem.media_type} was provided.")

        # check counter limit

        with Session(engine) as session:
            statement = select(ShareLimits).where(ShareLimits.action == action_config.name)
            results = session.scalars(statement)
            result = results.one_or_none()

        current_shares = result.count if result else 0
        last_used_at = result.last_used_at if result else None

        if self.is_quota_exceeded(current_shares, action_config.processing.max_shares):
            sse_service.dispatch_event(
                SseEventTranslateableFrontendNotification(
                    color="negative",
                    message_key="share.quota_exceeded",
                    context_data={"action_name": action_config.name, "quota": str(action_config.processing.max_shares)},
                )
            )

            raise BlockingIOError("Maximum number of Share/Print reached!")

        # block queue new prints until configured time is over
        remaining_s = self.remaining_time_blocked(action_config.processing.share_blocked_time, last_used_at)
        if remaining_s > 0:
            sse_service.dispatch_event(
                SseEventTranslateableFrontendNotification(
                    color="info",
                    message_key="share.blocked_request_ignored",
                    context_data={"remaining_s": f"{remaining_s:0.0f}"},
                )
            )

            raise BlockingIOError(f"Request ignored! Wait {remaining_s:.0f}s before trying again.")

        printer_name = action_config.processing.printer_name

        # once unblocked, also check printer availability if configured:
        if action_config.processing.check_if_printer_is_idle:
            try:
                printer_state, printer_state_raw = get_printer_status(printer_name)
                logger.debug(f"checked {printer_state=}, {printer_state_raw=}")
            except Exception as exc:
                raise RuntimeError(f"Failed getting printer status, error: {exc}! Maybe the printer '{printer_name}' does not exist?") from exc

            if printer_state is not PrinterStatus.OK:
                logger.warning(f"Print command failed because PrinterStatus is not OK, error: {printer_state_raw}")
                sse_service.dispatch_event(
                    SseEventTranslateableFrontendNotification(
                        color="negative",
                        message_key="share.printer_not_ready",
                        context_data={"action_name": action_config.name, "printer_name": printer_name},
                    )
                )
                raise BlockingIOError(f"Printer {printer_name} is not available! Please check power, connectivity, paper and cartridges.")

        builtin_placeholders = {
            "filename": mediaitem.processed.absolute(),
            "media_type": mediaitem.media_type,
            "action_config_name": action_config.name,
            "printer_name": printer_name,
        }

        configured_parameters = {}
        for parameter in action_config.processing.parameters:
            if parameter.key in builtin_placeholders:
                raise RuntimeError(f"Share parameter {parameter.key!r} conflicts with a built-in command placeholder.")
            if parameter.key in configured_parameters:
                raise RuntimeError(f"Share parameter {parameter.key!r} is configured more than once.")
            configured_parameters[parameter.key] = parameter

        # built-in placeholders can't be configured, so supplying one is rejected as unknown here
        supplied_parameters = parameters or {}
        unknown_parameters = supplied_parameters.keys() - configured_parameters.keys()
        if unknown_parameters:
            raise ShareParameterError(f"Unknown share parameter(s): {', '.join(sorted(unknown_parameters))}")

        share_parameters = {key: parameter.default for key, parameter in configured_parameters.items()}
        for key, value in supplied_parameters.items():
            parameter = configured_parameters[key]
            if len(value) > MAX_SHARE_INPUT_LENGTH:
                raise ShareParameterError(f"Share parameter {key!r} must be at most {MAX_SHARE_INPUT_LENGTH} characters.")

            try:
                valid_min = int(parameter.valid_min) if parameter.valid_min else None
                valid_max = int(parameter.valid_max) if parameter.valid_max else None
            except ValueError as exc:
                raise RuntimeError(f"Invalid bounds configured for share parameter {key!r}.") from exc

            if parameter.ui_type == "int":
                try:
                    int_value = int(value)
                except ValueError as exc:
                    raise ShareParameterError(f"Share parameter {key!r} must be an integer.") from exc

                if valid_min is not None and int_value < valid_min:
                    raise ShareParameterError(f"Share parameter {key!r} must be at least {valid_min}.")
                if valid_max is not None and int_value > valid_max:
                    raise ShareParameterError(f"Share parameter {key!r} must be at most {valid_max}.")
            else:
                if valid_min is not None and len(value) < valid_min:
                    raise ShareParameterError(f"Share parameter {key!r} must be at least {valid_min} characters.")
                if valid_max is not None and len(value) > valid_max:
                    raise ShareParameterError(f"Share parameter {key!r} must be at most {valid_max} characters.")

            share_parameters[key] = value

        logger.info("share parameters supplied for keys: %s", sorted(supplied_parameters))

        try:
            command_template = shlex.split(action_config.processing.share_command)
            if not command_template:
                raise RuntimeError("Share command configuration must not be empty.")
            format_values = {**builtin_placeholders, **share_parameters}
            command = [argument.format(**format_values) for argument in command_template]
        except KeyError as exc:
            raise RuntimeError(f"Error in configuration! Parameter {exc} is defined in command but was not configured as parameter!") from exc
        except TypeError as exc:
            raise RuntimeError(f"Error in configuration! Probably illegal parameter name defined, error: {exc}") from exc
        except ValueError as exc:
            raise RuntimeError(f"Invalid share command configuration: {exc}") from exc

        logger.info("executing share action %r", action_config.name)

        sse_service.dispatch_event(
            SseEventTranslateableFrontendNotification(
                color="positive",
                message_key="share.process_started",
                context_data={"action_name": action_config.name},
                spinner=True,
            )
        )

        try:
            completed_process = subprocess.run(
                command,
                capture_output=True,
                check=True,
                timeout=TIMEOUT_PROCESS_RUN,
            )

        except subprocess.CalledProcessError as exc:
            logger.error("Share command failed with return code %s", exc.returncode)
            logger.error("stdout: %s", exc.stdout)
            logger.error("stderr: %s", exc.stderr)

            sse_service.dispatch_event(SseEventTranslateableFrontendNotification(color="negative", message_key="share.process_failed"))

            raise ShareCommandError("Share command failed.") from exc

        except Exception as exc:
            # other errors (timeout, OSError, etc.)
            logger.exception("Unexpected error running share command")
            raise ShareCommandError("Share command failed.") from exc

        else:
            logger.info(f"cmd={completed_process.args}")
            logger.info(f"stdout={completed_process.stdout.decode(errors='replace')}")
            logger.debug(f"stderr={completed_process.stderr.decode(errors='replace')}")
            logger.info(f"command started successfully {mediaitem}")

        updated_current_shares = self.limit_counter_increment(action_config.name)

        if action_config.processing.max_shares > 0:
            # quota is enabled.
            sse_service.dispatch_event(
                SseEventTranslateableFrontendNotification(
                    color="info",
                    message_key="share.quota_notification",
                    context_data={
                        "action_name": action_config.name,
                        "current_shares": str(updated_current_shares),
                        "quota": str(action_config.processing.max_shares),
                    },
                )
            )

    def limit_counter_reset(self, field: str):
        try:
            with Session(engine) as session:
                statement = delete(ShareLimits).where(ShareLimits.action == field)
                result = cast(CursorResult, session.execute(statement))
                session.commit()

                logger.info(f"deleted {result.rowcount} items from ShareLimits")

        except Exception as exc:
            raise RuntimeError(f"failed to reset {field}, error: {exc}") from exc

    def limit_counter_reset_all(self):
        try:
            with Session(engine) as session:
                statement = delete(ShareLimits)
                result = cast(CursorResult, session.execute(statement))
                session.commit()
                logger.info(f"deleted {result.rowcount} entries from ShareLimits")

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
