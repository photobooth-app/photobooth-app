#!/usr/bin/python3
"""
Photobooth Application start script
"""
import logging
import multiprocessing
import socket
from pathlib import Path

import uvicorn
from dependency_injector.wiring import Provide, inject

from photobooth.__version__ import __version__
from photobooth.application import app

from .appconfig import AppConfig
from .containers import ApplicationContainer
from .services.loggingservice import LoggingService

logger = logging.getLogger(f"{__name__}")


@inject
def _server(
    config: AppConfig = Provide[ApplicationContainer.config],
    logging_service: LoggingService = Provide[ApplicationContainer.logging_service],
) -> uvicorn.Server:
    logger.info("Welcome to photobooth-app")

    # set spawn for all systems (defaults fork on linux currently and spawn on windows platform)
    # spawn will be the default for all systems in future so it's set here now to have same
    # results on all platforms

    multiprocessing_start_method = multiprocessing.get_start_method(allow_none=True)
    logger.info(f"{multiprocessing_start_method=}")
    # multiprocessing.set_start_method(method="spawn", force=True)
    # multiprocessing_start_method = multiprocessing.get_start_method(allow_none=True)
    # logger.info(f"{multiprocessing_start_method=}, forced")

    # log_level="trace", default info
    server = uvicorn.Server(
        uvicorn.Config(
            app=app,
            host=config.common.webserver_bind_ip,
            port=config.common.webserver_port,
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
    logging_service.uvicorn()

    return server


def main(run_server: bool = True):
    # guard to start only one instance at a time.
    try:
        s = socket.socket()
        s.bind(("localhost", 19988))  # bind fails on second instance, raising OSError
    except OSError as exc:
        print("startup aborted. another instance is running. exiting.")
        logger.critical("startup aborted. another instance is running. exiting.")
        raise SystemExit("only one instance allowed") from exc


    #application_container = ApplicationContainer()
    application_container: ApplicationContainer=app.container

    # use to construct paths in app referring to assets
    logger.info(f"photobooth directory: {Path(__file__).parent.resolve()}")
    # use to construct paths to user data
    logger.info(f"working directory: {Path.cwd().resolve()}")
    logger.info(f"app version started: {__version__}")

    application_container.wire(modules=[__name__], packages=[".routers"])

    ## init resources actively since they would not be initialized otherwise because just receive events
    # application_container.services.init_resources() # no global init as this would init all backends (even unused)
    application_container.services().gpio_service.init()
    application_container.services().information_service.init()
    application_container.services().keyboard_service.init()
    application_container.services().share_service.init()
    application_container.services().wled_service.init()

    # start main application
    server = _server()


    # serve, loops endless
    # this one is not executed in tests because it's not stoppable from within
    if run_server:
        server.run()

    # close single instance port
    s.close()

    application_container.shutdown_resources()


if __name__ == "__main__":
    main()
