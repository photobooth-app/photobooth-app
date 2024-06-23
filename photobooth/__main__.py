#!/usr/bin/python3
"""
Photobooth Application start script
"""

import logging
import os
from pathlib import Path

import uvicorn

from .__version__ import __version__
from .application import app
from .container import container
from .services.config import appconfig

logger = logging.getLogger(f"{__name__}")


def _create_basic_folders():
    os.makedirs("media", exist_ok=True)
    os.makedirs("userdata", exist_ok=True)
    os.makedirs("log", exist_ok=True)
    os.makedirs("config", exist_ok=True)
    os.makedirs("tmp", exist_ok=True)


def main(run_server: bool = True):
    try:
        _create_basic_folders()
    except Exception as exc:
        logger.critical(f"cannot create data folders, error: {exc}")
        raise RuntimeError(f"cannot create data folders, error: {exc}") from exc

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
            host=appconfig.common.webserver_bind_ip,
            port=appconfig.common.webserver_port,
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
    main()
