import logging
import time
from collections.abc import Generator
from pathlib import Path
from unittest.mock import patch

import pytest

from photobooth.appconfig import appconfig
from photobooth.container import Container, container
from photobooth.database.models import Mediaitem
from photobooth.database.types import MediaitemTypes
from photobooth.services.config.groups.share import ShareConfigurationSet, ShareProcessing
from photobooth.services.config.models.trigger import Trigger
from photobooth.utils.exceptions import WrongMediaTypeError

logger = logging.getLogger(name=None)


@pytest.fixture(scope="function")
def _container() -> Generator[Container, None, None]:
    container.start()

    # Setup
    appconfig.share.sharing_enabled = True
    appconfig.share.actions.clear()
    appconfig.share.actions.append(
        ShareConfigurationSet(
            name="share_action_infin",
            handles_images_only=False,
            processing=ShareProcessing(share_command="", share_blocked_time=0, max_shares=0),
            trigger=Trigger(),
        )
    )
    appconfig.share.actions.append(
        ShareConfigurationSet(
            name="share_action_blocked_2",
            handles_images_only=False,
            processing=ShareProcessing(share_command="", share_blocked_time=2, max_shares=0),
            trigger=Trigger(),
        )
    )
    appconfig.share.actions.append(
        ShareConfigurationSet(
            name="share_action_max_2",
            handles_images_only=False,
            processing=ShareProcessing(share_command="", share_blocked_time=0, max_shares=2),
            trigger=Trigger(),
        )
    )
    appconfig.share.actions.append(
        ShareConfigurationSet(
            name="share_action_handles_images_only",
            handles_images_only=True,
            processing=ShareProcessing(share_command="", share_blocked_time=0, max_shares=0),
            trigger=Trigger(),
        )
    )
    container.share_service.limit_counter_reset_all()

    yield container
    container.stop()


@patch("subprocess.run")
def test_print_service_disabled(mock_run, _container: Container):
    """test answer when disabled globally"""

    appconfig.share.sharing_enabled = False

    with pytest.raises(ConnectionRefusedError):
        _container.share_service.share(Mediaitem(media_type=MediaitemTypes.image, unprocessed=Path("1.jpg"), processed=Path("1.jpg")), 0)

    assert mock_run.assert_not_called


@patch("subprocess.run")
def test_print_image(mock_run, _container: Container):
    """enable service and try to print"""

    _container.share_service.share(Mediaitem(media_type=MediaitemTypes.image, unprocessed=Path("1.jpg"), processed=Path("1.jpg")), 0)

    # check subprocess.run was invoked
    mock_run.assert_called_once()


@patch("subprocess.run")
def test_print_image_blocked(mock_run, _container: Container):
    """enable service and try to print, check that it repsonds blocking correctly"""

    # two prints issued
    _container.share_service.share(Mediaitem(media_type=MediaitemTypes.image, unprocessed=Path("1.jpg"), processed=Path("1.jpg")), 1)
    time.sleep(2.5)

    _container.share_service.share(Mediaitem(media_type=MediaitemTypes.image, unprocessed=Path("1.jpg"), processed=Path("1.jpg")), 1)
    time.sleep(1)
    with pytest.raises(BlockingIOError):
        _container.share_service.share(Mediaitem(media_type=MediaitemTypes.image, unprocessed=Path("1.jpg"), processed=Path("1.jpg")), 1)

    # check subprocess.run was invoked
    assert mock_run.call_count == 2


@patch("subprocess.run")
def test_is_limited_exceeded(mock_run, _container: Container):
    """Test is_limited when max_shares is 0, meaning no limit."""
    test_action_index = 2
    # fake share used before.
    for _ in range(appconfig.share.actions[test_action_index].processing.max_shares):
        _container.share_service.limit_counter_increment(appconfig.share.actions[test_action_index].name)

    with pytest.raises(BlockingIOError):
        _container.share_service.share(
            Mediaitem(media_type=MediaitemTypes.image, unprocessed=Path("1.jpg"), processed=Path("1.jpg")), test_action_index
        )

    # command was not called, means quota exceeded.
    assert mock_run.assert_not_called


@patch("subprocess.run")
def test_print_wrong_mediatype_raises(mock_run, _container: Container):
    """enable service and try to print, check that it repsonds blocking correctly"""

    # video fails for images only action
    with pytest.raises(WrongMediaTypeError):
        _container.share_service.share(Mediaitem(media_type=MediaitemTypes.video, unprocessed=Path("1.mp4"), processed=Path("1.mp4")), 3)
    # animation
    with pytest.raises(WrongMediaTypeError):
        _container.share_service.share(Mediaitem(media_type=MediaitemTypes.animation, unprocessed=Path("1.gif"), processed=Path("1.gif")), 3)
    # multicamera
    with pytest.raises(WrongMediaTypeError):
        _container.share_service.share(Mediaitem(media_type=MediaitemTypes.multicamera, unprocessed=Path("1.gif"), processed=Path("1.gif")), 3)

    # check subprocess.run was not invoked
    assert mock_run.call_count == 0

    # image
    _container.share_service.share(Mediaitem(media_type=MediaitemTypes.image, unprocessed=Path("1.jpg"), processed=Path("1.jpg")), 3)

    # collage
    _container.share_service.share(Mediaitem(media_type=MediaitemTypes.collage, unprocessed=Path("1.jpg"), processed=Path("1.jpg")), 3)

    # check subprocess.run was not invoked
    assert mock_run.call_count == 2
