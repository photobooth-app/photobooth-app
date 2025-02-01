import logging

from photobooth.plugins.hookspecs import hookimpl

logger = logging.getLogger(__name__)


class UserpluginExample:
    def __init__(self):
        super().__init__()

    @hookimpl
    def start(self):
        print("start CALLED!!!")
