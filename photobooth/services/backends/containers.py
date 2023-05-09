import logging

from dependency_injector import containers, providers
from pymitter import EventEmitter

from .simulated import SimulatedBackend
from .webcamcv2 import WebcamCv2Backend

logger = logging.getLogger(__name__)


class BackendsContainer(containers.DeclarativeContainer):
    evtbus = providers.Dependency(instance_of=EventEmitter)
    config = providers.Configuration()

    ## Services: Backends (for image aquisition)
    disabled_backend = providers.Object(None)
    simulated_backend = providers.Singleton(SimulatedBackend, evtbus)
    webcamcv2_backend = providers.Singleton(WebcamCv2Backend, evtbus)
    picamera2_backend = providers.Object(None)
    gphoto2_backend = providers.Object(None)
    webcamv4l_backend = providers.Object(None)

    backends_set = {
        "disabled": disabled_backend,
        "simulated": simulated_backend,
        "webcamcv2": webcamcv2_backend,
        "picamera2": picamera2_backend,
        "gphoto2": gphoto2_backend,
        "webcamv4l": webcamv4l_backend,
    }

    # picamera2 backend import
    try:
        from .picamera2 import Picamera2Backend

        backends_set.update(
            {"picamera2": providers.Singleton(Picamera2Backend, evtbus)}
        )
    except Exception:
        logger.info("skipped import picamera2 backend")

    # gphoto2 backend import
    try:
        from .gphoto2 import Gphoto2Backend

        backends_set.update({"gphoto2": providers.Singleton(Gphoto2Backend, evtbus)})
    except Exception:
        logger.info("skipped import gphoto2 backend")

    # gphoto2 backend import
    try:
        from .webcamv4l import WebcamV4lBackend

        backends_set.update(
            {"webcamv4l": providers.Singleton(WebcamV4lBackend, evtbus)}
        )
    except Exception:
        logger.info("skipped import webcamv4l backend")

    logger.info(f"available backends: TODO: {False}")
    # FIXME: Logger at this point not inited yet! log messages not visible!
    print(backends_set)

    # following are to be used in aquisitionservice
    primary_backend = providers.Selector(
        providers.Callable(
            lambda cfg_enum: cfg_enum.lower(), cfg_enum=config.backends.MAIN_BACKEND
        ),
        **backends_set,
    )
    secondary_backend = providers.Selector(
        providers.Callable(
            lambda cfg_enum: cfg_enum.lower(), cfg_enum=config.backends.LIVE_BACKEND
        ),
        **backends_set,
    )
