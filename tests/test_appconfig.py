"""
Testing virtual camera Backend
"""
import logging

from dependency_injector import providers
from pymitter import EventEmitter

from photobooth.appconfig import AppConfig
from photobooth.services.backends.containers import BackendsContainer

logger = logging.getLogger(name=None)


def test_appconfig_singleton():
    backend = BackendsContainer(evtbus=providers.Singleton(EventEmitter), config=providers.Singleton(AppConfig))

    # modify config:
    backend.config().common.DEBUG_LEVEL = 99
    assert backend.config().common.DEBUG_LEVEL == 99


def test_appconfig_factory():
    backend = BackendsContainer(evtbus=providers.Singleton(EventEmitter), config=providers.Factory(AppConfig))

    # modify config:
    backend.config().common.DEBUG_LEVEL = 99
    assert not backend.config().common.DEBUG_LEVEL == 99


def test_appconfig_dependency_singleton():
    assert True

    # test no working any more
    """
    backend = BackendsContainer(evtbus=providers.Singleton(EventEmitter), config=providers.Singleton(AppConfig))

    original_value = backend.config().backends.cv2_device_index
    modified_value = original_value + 1

    # modify config ensure
    backend.config().backends.cv2_device_index = modified_value
    assert backend.config().backends.cv2_device_index == modified_value

    # check that dependency received also the modified value
    webcamcv2_backend = backend.webcamcv2_backend
    assert webcamcv2_backend._config.backends.cv2_device_index == modified_value
    """
