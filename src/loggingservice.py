""" 
Control logging for the app
"""

import os
import logging
import datetime
import json
from logging.handlers import RotatingFileHandler
from logging import LogRecord
from pymitter import EventEmitter
from src.configsettings import settings


class EventstreamLogHandler(logging.Handler):
    """
    Logging handler to emit events to eventstream;
    to be displayed in console.log on browser frontend
    """

    def __init__(self, evtbus: EventEmitter):
        self._evtbus = evtbus

        self._initlogrecords_emitted = False
        self._initlogrecords = []

        self._evtbus.on("publishSSE/initial", self._emit_initlogs)

        logging.Handler.__init__(self)

    def _emit_initlogs(self):
        for logrecord in self._initlogrecords:
            self._evtbus.emit(
                "publishSSE", sse_event="logrecord", sse_data=json.dumps(logrecord)
            )
        # stop adding new records
        self._initlogrecords_emitted = True

        # self._initlogrecords = []

    def emit(self, record: LogRecord):
        logrecord = {
            "time": datetime.datetime.fromtimestamp(record.created).strftime(
                "%d.%b.%y %H:%M:%S"
            ),
            "level": record.levelname,
            "message": record.getMessage(),
            "name": record.name,
            "funcName": record.funcName,
            "lineno": record.lineno,
        }

        if not self._initlogrecords_emitted and len(self._initlogrecords) < 50:
            # after logrecords were first time emitted to client via eventstream,
            # not add any new records to array.
            # only log first 50 messgaes to not pollute the sse queue
            self._initlogrecords.append(logrecord)

        self._evtbus.emit(
            "publishSSE", sse_event="logrecord", sse_data=json.dumps(logrecord)
        )


class LoggingService:
    """_summary_"""

    def __init__(self, evtbus: EventEmitter):
        fmt = "%(asctime)s [%(levelname)s] %(name)s %(funcName)s() L%(lineno)-4d %(message)s"
        log_formatter = logging.Formatter(fmt=fmt)

        logging.basicConfig(level=logging.DEBUG, format=fmt, force=True)

        # our default logger (root = None)
        # root loggers seems to be the template for all other loggers,
        # that are not in __name__ namespace. not too verbose here
        root_logger = logging.getLogger(name=None)
        # Remove all handlers associated with the root logger object.
        # for handler in logging.root.handlers[:]:
        #    logging.root.removeHandler(handler)
        root_logger.setLevel(settings.common.DEBUG_LEVEL.value)

        # our default logger (not root, root would be None)
        main_logger = logging.getLogger(name="__main__")
        main_logger.setLevel(settings.common.DEBUG_LEVEL.value)
        # stop propagating here, so root does not receive __main__'s messages avoiding duplicates
        # mainLogger.propagate = False

        # create console handler
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(log_formatter)

        # create rotatingFileHandler
        rotatingfile_handler = RotatingFileHandler(
            filename="./log/qbooth.log", maxBytes=1024**2, backupCount=10
        )
        rotatingfile_handler.setFormatter(log_formatter)

        # create rotatingFileHandler
        eventstream_handler = EventstreamLogHandler(evtbus=evtbus)
        eventstream_handler.setFormatter(log_formatter)

        # add ch to logger
        # rootLogger.addHandler(consoleHandler)
        root_logger.addHandler(rotatingfile_handler)
        root_logger.addHandler(eventstream_handler)
        # mainLogger.addHandler(consoleHandler)
        main_logger.addHandler(rotatingfile_handler)
        main_logger.addHandler(eventstream_handler)

        # loggers_defined = [logging.getLogger(name)
        #                   for name in logging.root.manager.loggerDict]
        # print(loggers_defined)

        self.other_loggers()

    def other_loggers(self):
        """_summary_"""
        for name in [
            "picamera2",
            "pywifi",
            "sse_starlette.sse",
            "src.Autofocus",
            "transitions.core",
            "PIL.PngImagePlugin",
        ]:
            # mute some other logger
            lgr = logging.getLogger(name=name)
            lgr.setLevel(logging.INFO)
            lgr.propagate = False

        os.environ["OPENCV_LOG_LEVEL"] = "ERROR"
