import logging

from statemachine import Event, State

from photobooth.plugins import hookimpl

logger = logging.getLogger(__name__)


class UserpluginExample:
    def __init__(self):
        super().__init__()

    @hookimpl
    def start(self):
        logger.warning("start CALLED!!!")

    @hookimpl
    def before_transition(self, source: State, target: State, event: Event):
        logger.warning(self)
        logger.warning(repr(source))
        logger.warning(repr(target))
        logger.warning(repr(event))
        logger.warning("state called in plugin!!!!")
