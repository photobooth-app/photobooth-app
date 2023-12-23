import logging

from dependency_injector import containers, providers

from ...appconfig import AppConfig
from .abstractbackend import AbstractBackend
from .digicamcontrol import DigicamcontrolBackend
from .virtualcamera import VirtualCameraBackend
from .webcamcv2 import WebcamCv2Backend

logger = logging.getLogger(__name__)


def init_res_obj_backend(_obj_: AbstractBackend, config: AppConfig):
    """actually same as in parent container."""
    _backend = None

    try:
        _backend = _obj_(config)
        _backend.start()
    except Exception as exc:
        logger.exception(exc)
        logger.critical("could not init/start backend")

    finally:
        yield _backend

    try:
        if _backend:  # if not none
            _backend.stop()
    except Exception as exc:
        logger.exception(exc)
        logger.critical("could not stop backend")


class BackendsContainer(containers.DeclarativeContainer):
    config = providers.Dependency(instance_of=AppConfig)

    ## Services: Backends (for image aquisition)
    disabled_backend = providers.Object(None)
    digicamcontrol_backend = providers.Resource(init_res_obj_backend, DigicamcontrolBackend, config)
    gphoto2_backend = providers.Object(None)
    picamera2_backend = providers.Object(None)
    virtualcamera_backend = providers.Resource(init_res_obj_backend, VirtualCameraBackend, config)
    webcamcv2_backend = providers.Resource(init_res_obj_backend, WebcamCv2Backend, config)
    webcamv4l_backend = providers.Object(None)

    # picamera2 backend import
    try:
        from .picamera2_ import Picamera2Backend

        picamera2_backend = providers.Resource(init_res_obj_backend, Picamera2Backend, config)
        print("added provider for picamera2 backend")
    except Exception:
        # logger is not avail at this point yet, so print:
        print("skipped import picamera2 backend")

    # gphoto2 backend import
    try:
        from .gphoto2 import Gphoto2Backend

        gphoto2_backend = providers.Resource(init_res_obj_backend, Gphoto2Backend, config)
        print("added provider for gphoto2 backend")
    except Exception:
        # logger is not avail at this point yet, so print:
        print("skipped import gphoto2 backend")

    # gphoto2 backend import
    try:
        from .webcamv4l import WebcamV4lBackend

        webcamv4l_backend = providers.Resource(init_res_obj_backend, WebcamV4lBackend, config)
        print("added provider for webcamv4l backend")
    except Exception:
        # logger is not avail at this point yet, so print:
        print("skipped import webcamv4l backend")

    # following are to be used in aquisitionservice

    backends_set = {
        "disabled": disabled_backend,
        "digicamcontrol": digicamcontrol_backend,
        "gphoto2": gphoto2_backend,
        "picamera2": picamera2_backend,
        "virtualcamera": virtualcamera_backend,
        "webcamcv2": webcamcv2_backend,
        "webcamv4l": webcamv4l_backend,
    }

    primary_backend = providers.Selector(
        providers.Callable(lambda cfg_enum: cfg_enum.backends.MAIN_BACKEND.lower(), cfg_enum=config),
        **backends_set,
    )

    secondary_backend = providers.Selector(
        providers.Callable(lambda cfg_enum: cfg_enum.backends.LIVE_BACKEND.lower(), cfg_enum=config),
        **backends_set,
    )
