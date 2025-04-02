#!/usr/bin/python3
"""
Photobooth Application start script
"""

import argparse
import logging
import sys
from pathlib import Path

import uvicorn

from .__version__ import __version__
from .database.database import create_db_and_tables

parser = argparse.ArgumentParser()
parser.add_argument("--host", action="store", type=str, default="0.0.0.0", help="Host the server is bound to (default: %(default)s).")
parser.add_argument("--port", action="store", type=int, default=8000, help="Port the server listens to (default: %(default)s).")

logger = logging.getLogger(f"{__name__}")


def main(args=None, run_server: bool = True):
    args = parser.parse_args(args)  # parse here, not above because pytest system exit 2

    # create all db before anything else...
    create_db_and_tables()

    from .application import app
    from .container import container

    host = args.host
    port = args.port

    logger.info("✨ Welcome to the photobooth-app ✨")

    logger.info(f"photobooth directory: {Path(__file__).parent.resolve()}")
    logger.info(f"working directory: {Path.cwd().resolve()}")
    logger.info(f"app version started: {__version__}")

    server = uvicorn.Server(uvicorn.Config(app=app, host=host, port=port, log_level="info", workers=None))

    # adjust logging after uvicorn setup
    container.logging_service.uvicorn()

    # start all services
    container.start()

    # serve, loops endless
    # this one is not executed in tests because it's not stoppable from within
    if run_server:
        try:
            server.run()
        except KeyboardInterrupt:
            print("got ctrl-c, photobooth-app 🔚")
            pass


if __name__ == "__main__":
    sys.exit(main(args=sys.argv[1:]))  # for testing
