#!/usr/bin/python3
"""
Photobooth Application start script
"""

import argparse
import logging
import sys
from pathlib import Path

import uvicorn
import mimetypes

from .__version__ import __version__
from .database.database import create_db_and_tables

parser = argparse.ArgumentParser()
parser.add_argument("--host", action="store", type=str, default="0.0.0.0", help="Host the server is bound to (default: %(default)s).")
parser.add_argument("--port", action="store", type=int, default=8000, help="Port the server listens to (default: %(default)s).")

logger = logging.getLogger(f"{__name__}")

mimetypes.add_type("application/javascript", ".js", True)

def main(args=None, run_server: bool = True):
    args = parser.parse_args(args)  # parse here, not above because pytest system exit 2

    # create all db before anything else...
    create_db_and_tables()

    from .application import app
    from .container import container

    host = args.host
    port = args.port

    # use to construct paths in app referring to assets
    logger.info(f"photobooth directory: {Path(__file__).parent.resolve()}")
    # use to construct paths to user data
    logger.info(f"working directory: {Path.cwd().resolve()}")
    logger.info(f"app version started: {__version__}")

    # start main application server
    logger.info("Welcome to the photobooth-app")  # TODO, could be used later:, extra={"display_notification": True})

    # log_level="trace", default info
    server = uvicorn.Server(
        uvicorn.Config(
            app=app,
            host=host,
            port=port,
            log_level="debug",
        )
    )

    # shutdown app workaround:
    # workaround until https://github.com/encode/uvicorn/issues/1579 is fixed and
    # shutdown can be handled properly.
    # Otherwise the stream.mjpg if open will block shutdown of the server
    # signal CTRL-C and systemctl stop would have no effect, app stalls
    # signal.signal(signal.SIGINT, signal_handler) and similar
    # don't work, because uvicorn is eating up signal handler
    # currently: https://github.com/encode/uvicorn/issues/1579
    # the workaround: currently we set force_exit to True to shutdown the server
    server.force_exit = True

    # adjust logging after uvicorn setup
    container.logging_service.uvicorn()

    # start all services
    container.start()

    # serve, loops endless
    # this one is not executed in tests because it's not stoppable from within
    if run_server:
        server.run()
    # else:
    #     container.stop()


if __name__ == "__main__":
    sys.exit(main(args=sys.argv[1:]))  # for testing
