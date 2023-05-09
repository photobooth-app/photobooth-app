import io
import logging

from PIL import Image
from pymitter import EventEmitter

from photobooth.appconfig import (
    AppConfig,
    EnumImageBackendsLive,
    EnumImageBackendsMain,
)
from photobooth.services.backends.containers import BackendsContainer
from photobooth.services.containers import ServicesContainer

logger = logging.getLogger(name=None)
"""
prepare config for testing
"""


def test_getimages_frommultiple_backends():
    # modify config:
    services = ServicesContainer(
        evtbus=EventEmitter(), settings=AppConfig(), backends=BackendsContainer()
    )
    services.config.backends.LIVEPREVIEW_ENABLED.from_value(True)
    services.config.backends.MAIN_BACKEND.from_value(EnumImageBackendsMain.SIMULATED)
    services.config.backends.LIVE_BACKEND.from_value(EnumImageBackendsLive.SIMULATED)

    aquisition_service = services.aquisition_service()
    aquisition_service.start()

    with Image.open(io.BytesIO(aquisition_service.wait_for_hq_image())) as img:
        img.verify()

    # TODO: test gen_stream()

    aquisition_service.stop()
