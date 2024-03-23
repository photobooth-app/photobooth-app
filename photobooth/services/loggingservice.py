"""
Control logging for the app
"""

import logging
import os
import sys
import threading
import time
from datetime import datetime
from logging import FileHandler, LogRecord
from pathlib import Path

from .baseservice import BaseService
from .config import appconfig
from .sseservice import SseEventLogRecord, SseService

LOG_DIR = "log"


class EventstreamLogHandler(logging.Handler):
    """
    Logging handler to emit events to eventstream;
    to be displayed in console.log on browser frontend

    TODO, could replace the FrontendNotification, also logs with extras used to control the UI:
      - record.display_notification (bool): Show the log in the UI or not.
    """

    def __init__(self, sse_service: SseService):
        self._sse_service = sse_service

        logging.Handler.__init__(self)

    def emit(self, record: LogRecord):
        sse_logrecord = SseEventLogRecord(
            time=datetime.fromtimestamp(record.created).strftime("%d.%b.%y %H:%M:%S"),
            level=record.levelname,
            message=record.getMessage(),
            name=record.name,
            funcName=record.funcName,
            lineno=record.lineno,
            # TODO: maybe later: display_notification=bool(getattr(record, "display_notification", False)),
            # if present display also in the UI as notification
        )

        self._sse_service.dispatch_event(sse_logrecord)


class LoggingService(BaseService):
    """_summary_"""

    debug_level = logging.DEBUG

    def __init__(self, sse_service: SseService):
        """Setup logger

        Args:
            sse_service (SseService): _description_
        """
        super().__init__(sse_service=sse_service)

        # ensure dir exists
        os.makedirs(LOG_DIR, exist_ok=True)

        ## formatter ##
        fmt = "%(asctime)s [%(levelname)8s] %(message)s (%(filename)s:%(lineno)s)"
        log_formatter = logging.Formatter(fmt=fmt)

        # filename per day to log to
        logfile = Path(LOG_DIR, f"photobooth_{datetime.now().astimezone().strftime('%Y%m%d')}.log")

        ## basic configuration
        # latest basicConfig adds a streamHandler output to console if not automatically called
        # earlier by some .warn .info or other
        # force=False because otherwise the pytest console logger stream handler gets deleted
        logging.basicConfig(level=logging.DEBUG, format=fmt, force=False, encoding="utf-8")
        logging.debug("loggingservice __init__ basicConfig set")
        logging.debug("loggingservice __init__ started")

        self.debug_level = appconfig.common.DEBUG_LEVEL.value

        ## logger
        # default logger (root = None or "")
        # root logger also to be the template for all other loggers,
        # that are created in the app at a later time during run
        root_logger = logging.getLogger(name=None)

        # set level based on users config
        root_logger.setLevel(self.debug_level)

        ## handler

        self.file_handler = FileHandler(filename=logfile, mode="a", encoding="utf-8", delay=True)
        self.file_handler.setFormatter(log_formatter)

        # create rotatingFileHandler
        self.eventstream_handler = EventstreamLogHandler(sse_service=sse_service)
        self.eventstream_handler.setFormatter(log_formatter)

        ## wire logger and handler ##
        root_logger.addHandler(self.file_handler)
        root_logger.addHandler(self.eventstream_handler)

        ## mute other loggers
        self.other_loggers()

        ## add the exepthooks
        sys.excepthook = self._handle_sys_exception
        threading.excepthook = self._handle_threading_exception
        # no solution to handle exceptions in sep processes yet...

        logging.debug("loggingservice __init__ finished")
        logging.debug(f"registered handlers: {logging.root.handlers}")

        self.remove_old_logs()

    def remove_old_logs(self):
        DAYS = 7
        critical_time = DAYS * 86400  # 7 days

        now = time.time()

        for item in Path(LOG_DIR).glob("*.log"):
            if item.is_file():
                if item.stat().st_mtime < (now - critical_time):
                    logging.info(f"deleting logfile older than {DAYS} days: {item}")
                    os.remove(item)

    def other_loggers(self):
        """mute some logger by rasing their log level"""

        for name in [
            "picamera2.picamera2",
            "sse_starlette.sse",
            "PIL.PngImagePlugin",
            "PIL.TiffImagePlugin",
            "multipart",
            "v4l2py",
            "requests",
            "urllib3",
        ]:
            # mute some other logger, by raising their debug level to INFO
            lgr = logging.getLogger(name=name)
            lgr.setLevel(logging.INFO)
            lgr.propagate = True

        for name in [
            "pywifi",
        ]:
            # mute some other logger, by raising their debug level to INFO
            lgr = logging.getLogger(name=name)
            lgr.setLevel(logging.WARNING)
            lgr.propagate = True

        os.environ["OPENCV_LOG_LEVEL"] = "ERROR"

    def uvicorn(self):
        """_summary_"""

        for name in [
            "uvicorn.error",
            "uvicorn.access",
            "uvicorn",
        ]:
            lgr = logging.getLogger(name=name)
            lgr.setLevel(self.debug_level)
            lgr.propagate = False
            lgr.handlers = [
                logging.root.handlers[0],  # this is the streamhandler if not in pytest.
                self.file_handler,
                self.eventstream_handler,
            ]

    @staticmethod
    def _handle_sys_exception(exc_type, exc_value, exc_traceback):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return

        logging.getLogger(name="__main__").exception(
            f"Uncaught exception: {exc_type} {exc_value}",
            exc_info=(exc_type, exc_value, exc_traceback),
        )

    @staticmethod
    def _handle_threading_exception(args: threading.ExceptHookArgs):
        # report the failure
        logging.getLogger(name="__main__").exception(
            f"Uncaught exception in thread {args.thread}: {args.exc_type} {args.exc_value}",
            exc_info=(args.exc_type, args.exc_value, args.exc_traceback),
        )
