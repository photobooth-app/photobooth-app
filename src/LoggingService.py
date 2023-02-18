import os
import logging
import json
from logging.handlers import RotatingFileHandler
from logging import LogRecord
from pymitter import EventEmitter
from ConfigSettings import settings

import datetime


class EventstreamLogHandler(logging.Handler):
    """
    Logging handler to emit events to eventstream; to be displayed in console.log on browser frontend
    """

    def __init__(self, ee: EventEmitter):
        self._ee = ee
        logging.Handler.__init__(self)

    def emit(self, record: LogRecord):

        logrecord = {
            "time": datetime.datetime.fromtimestamp(record.created).strftime("%d.%b.%y %H:%M:%S"),
            'level': record.levelname,
            'message': record.getMessage(),
            'name': record.name,
            'funcName': record.funcName,
            'lineno': record.lineno,
        }
        self._ee.emit("publishSSE", sse_event="logrecord",
                      sse_data=json.dumps(logrecord))


class LoggingService():
    def __init__(self, ee: EventEmitter):
        fmt = '%(asctime)s [%(levelname)s] %(name)s %(funcName)s() L%(lineno)-4d %(message)s'
        logFormatter = logging.Formatter(fmt=fmt)

        logging.basicConfig(level=logging.DEBUG,
                            format=fmt, force=True)

        # our default logger (root = None)
        # root loggers seems to be the template for all other loggers, that are not in __name__ namespace. not too verbose here
        rootLogger = logging.getLogger(name=None)
        # Remove all handlers associated with the root logger object.
        # for handler in logging.root.handlers[:]:
        #    logging.root.removeHandler(handler)
        rootLogger.setLevel(settings.common.DEBUG_LEVEL)

        # our default logger (not root, root would be None)
        mainLogger = logging.getLogger(name="__main__")
        mainLogger.setLevel(settings.common.DEBUG_LEVEL)
        # stop propagating here, so root does not receive __main__'s messages avoiding duplicates
        # mainLogger.propagate = False

        # create console handler
        consoleHandler = logging.StreamHandler()
        consoleHandler.setFormatter(logFormatter)

        # create rotatingFileHandler
        rotatingFileHandler = RotatingFileHandler(
            filename="./log/qbooth.log",
            maxBytes=1024**2,
            backupCount=10)
        rotatingFileHandler.setFormatter(logFormatter)

        # create rotatingFileHandler
        eventStreamHandler = EventstreamLogHandler(ee=ee)
        eventStreamHandler.setFormatter(logFormatter)

        # add ch to logger
        # rootLogger.addHandler(consoleHandler)
        rootLogger.addHandler(rotatingFileHandler)
        rootLogger.addHandler(eventStreamHandler)
        # mainLogger.addHandler(consoleHandler)
        mainLogger.addHandler(rotatingFileHandler)
        mainLogger.addHandler(eventStreamHandler)

        loggers_defined = [logging.getLogger(name)
                           for name in logging.root.manager.loggerDict]
        # print(loggers_defined)

        """# reconfigure if any changes from config needs to be applied.
        logging.config.dictConfig(ConfigSettingsInternal().logger.LOGGER_CONFIG)
        for handles in logging.getLogger().handlers:
            # after configure, set all handlers level to global requested level:
            handles.setLevel(settings.common.DEBUG_LEVEL)
            print(handles)
        """
        self.otherLoggers()

    def otherLoggers(self):
        for name in ["picamera2", "pywifi", "sse_starlette.sse", "src.Autofocus", "transitions.core", "PIL.PngImagePlugin"]:
            # mute some other logger
            lgr = logging.getLogger(name=name)
            lgr.setLevel(logging.INFO)
            lgr.propagate = False

        os.environ["OPENCV_LOG_LEVEL"] = "ERROR"
