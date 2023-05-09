import logging
import time

import pytest
from dependency_injector import providers
from pymitter import EventEmitter

from photobooth.appconfig import AppConfig
from photobooth.services.containers import ServicesContainer

logger = logging.getLogger(name=None)


def test_disabled():
    """should just fail in silence if disabled but app triggers some presets"""

    services = ServicesContainer(
        evtbus=providers.Singleton(EventEmitter),
        config=providers.Singleton(AppConfig),
    )
    services.config().wled.ENABLED = False

    try:
        wled_service = services.wled_service()

        # test this, because should be ignored, no error
        wled_service.preset_standby()

    except Exception as exc:
        raise AssertionError("init failed") from exc


def test_enabled_nonexistentserialport():
    """should just fail in silence if disabled but app triggers some presets"""

    services = ServicesContainer(
        evtbus=providers.Singleton(EventEmitter),
        config=providers.Singleton(AppConfig),
    )
    services.config().wled.ENABLED = True
    services.config().wled.SERIAL_PORT = "nonexistentserialport"

    with pytest.raises(RuntimeError):
        # getting service starts automatically. here an Runtime Exception shall be thrown if connection fails.
        services.wled_service()


def test_restart_class():
    services = ServicesContainer(
        evtbus=providers.Singleton(EventEmitter),
        config=providers.Singleton(AppConfig),
    )

    logger.debug("getting service, starting resource")
    services.wled_service()

    logger.debug("shutdown resource")
    services.wled_service.shutdown()

    logger.debug("getting service, starting resource again")
    services.wled_service()


def test_change_presets():
    services = ServicesContainer(
        evtbus=providers.Singleton(EventEmitter),
        config=providers.Singleton(AppConfig),
    )

    logger.debug("getting service, starting resource")
    wled_service = services.wled_service()

    time.sleep(1)

    wled_service.preset_thrill()
    time.sleep(2)
    wled_service.preset_shoot()
    time.sleep(1)
    wled_service.preset_standby()
    time.sleep(0.5)
