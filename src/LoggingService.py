import os
import logging
from logging.handlers import RotatingFileHandler
from pymitter import EventEmitter
from ConfigSettings import settings


class EventstreamLogHandler(logging.Handler):
    """
    Logging handler to emit events to eventstream; to be displayed in console.log on browser frontend
    """

    def __init__(self, ee: EventEmitter):
        self._ee = ee
        logging.Handler.__init__(self)

    def emit(self, record):
        self._ee.emit("publishSSE", sse_event="message",
                      sse_data=self.format(record))


class LoggingService():
    def __init__(self, ee: EventEmitter):
        logging.basicConfig(level=logging.DEBUG,
                            format='%(asctime)s [%(levelname)s] %(name)s %(funcName)s() L%(lineno)-4d %(message)s', force=True)

        # our default logger (root = None)
        # root loggers seems to be the template for all other loggers, that are not in __name__ namespace. not too verbose here
        rootLogger = logging.getLogger(name=None)
        # Remove all handlers associated with the root logger object.
        # for handler in logging.root.handlers[:]:
        #    logging.root.removeHandler(handler)
        rootLogger.setLevel(settings.debugging.DEBUG_LEVEL)

        # our default logger (not root, root would be None)
        mainLogger = logging.getLogger(name="__main__")
        mainLogger.setLevel(settings.debugging.DEBUG_LEVEL)
        # stop propagating here, so root does not receive __main__'s messages avoiding duplicates
        # mainLogger.propagate = False

        # create console handler
        consoleHandler = logging.StreamHandler()
        # consoleHandler.setFormatter(formatter)

        # create rotatingFileHandler
        rotatingFileHandler = RotatingFileHandler(
            filename="./log/qbooth.log",
            maxBytes=1024**2,
            backupCount=10)
        # rotatingFileHandler.setFormatter(formatter)

        # create rotatingFileHandler
        eventStreamHandler = EventstreamLogHandler(ee=ee)
        # eventStreamHandler.setFormatter(formatter)

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
            handles.setLevel(settings.debugging.DEBUG_LEVEL)
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
