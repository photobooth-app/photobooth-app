import logging
import subprocess
import time
from collections.abc import Generator
from pathlib import Path
from unittest.mock import patch

import pytest
from sqlalchemy.orm import Session

from photobooth.appconfig import appconfig
from photobooth.container import Container, container
from photobooth.database.database import engine
from photobooth.database.models import Mediaitem, ShareLimits
from photobooth.services.config.groups.share import ShareConfigurationSet, ShareProcessing, ShareProcessingParameters
from photobooth.services.config.models.trigger import Trigger
from photobooth.utils.exceptions import ShareCommandError, ShareParameterError, WrongMediaTypeError

logger = logging.getLogger(name=None)


@pytest.fixture(scope="function")
def _container() -> Generator[Container, None, None]:

    # Setup
    appconfig.share.sharing_enabled = True
    appconfig.share.actions.clear()
    appconfig.share.actions.append(
        ShareConfigurationSet(
            name="share_action_infin",
            handles_images_only=False,
            processing=ShareProcessing(share_command="echo {filename}", share_blocked_time=0, max_shares=0),
            trigger=Trigger(),
        )
    )
    appconfig.share.actions.append(
        ShareConfigurationSet(
            name="share_action_blocked_2",
            handles_images_only=False,
            processing=ShareProcessing(share_command="echo {filename}", share_blocked_time=2, max_shares=0),
            trigger=Trigger(),
        )
    )
    appconfig.share.actions.append(
        ShareConfigurationSet(
            name="share_action_max_2",
            handles_images_only=False,
            processing=ShareProcessing(share_command="echo {filename}", share_blocked_time=0, max_shares=2),
            trigger=Trigger(),
        )
    )
    appconfig.share.actions.append(
        ShareConfigurationSet(
            name="share_action_handles_images_only",
            handles_images_only=True,
            processing=ShareProcessing(share_command="echo {filename}", share_blocked_time=0, max_shares=0),
            trigger=Trigger(),
        )
    )
    container.share_service.limit_counter_reset_all()

    container.reload()
    yield container
    container.stop()


@patch("subprocess.run")
def test_print_service_disabled(mock_run, _container: Container):
    """test answer when disabled globally"""

    appconfig.share.sharing_enabled = False

    with pytest.raises(ConnectionRefusedError):
        _container.share_service.share(Mediaitem(media_type="image", processed=Path("1.jpg")), 0)

    assert mock_run.assert_not_called


@patch("subprocess.run")
def test_print_image(mock_run, _container: Container):
    """enable service and try to print"""

    _container.share_service.share(Mediaitem(media_type="image", processed=Path("1.jpg")), 0)

    # check subprocess.run was invoked
    mock_run.assert_called_once()


@patch("subprocess.run")
def test_print_image_blocked(mock_run, _container: Container):
    """enable service and try to print, check that it repsonds blocking correctly"""

    # two prints issued
    _container.share_service.share(Mediaitem(media_type="image", processed=Path("1.jpg")), 1)
    time.sleep(2.5)

    _container.share_service.share(Mediaitem(media_type="image", processed=Path("1.jpg")), 1)
    time.sleep(1)
    with pytest.raises(BlockingIOError):
        _container.share_service.share(Mediaitem(media_type="image", processed=Path("1.jpg")), 1)

    # check subprocess.run was invoked
    share_command_calls = [call for call in mock_run.call_args_list if call.args and call.args[0][0] == "echo"]
    assert len(share_command_calls) == 2


@patch("subprocess.run")
def test_is_limited_exceeded(mock_run, _container: Container):
    """Test is_limited when max_shares is 0, meaning no limit."""
    test_action_index = 2
    # fake share used before.
    for _ in range(appconfig.share.actions[test_action_index].processing.max_shares):
        _container.share_service.limit_counter_increment(appconfig.share.actions[test_action_index].name)

    with pytest.raises(BlockingIOError):
        _container.share_service.share(Mediaitem(media_type="image", processed=Path("1.jpg")), test_action_index)

    # command was not called, means quota exceeded.
    assert mock_run.assert_not_called


@patch("subprocess.run")
def test_print_wrong_mediatype_raises(mock_run, _container: Container):
    """enable service and try to print, check that it repsonds blocking correctly"""

    # video fails for images only action
    with pytest.raises(WrongMediaTypeError):
        _container.share_service.share(Mediaitem(media_type="video", processed=Path("1.mp4")), 3)
    # animation
    with pytest.raises(WrongMediaTypeError):
        _container.share_service.share(Mediaitem(media_type="animation", processed=Path("1.gif")), 3)
    # multicamera
    with pytest.raises(WrongMediaTypeError):
        _container.share_service.share(Mediaitem(media_type="multicamera", processed=Path("1.gif")), 3)

    # check subprocess.run was not invoked
    assert mock_run.call_count == 0

    # image
    _container.share_service.share(Mediaitem(media_type="image", processed=Path("1.jpg")), 3)

    # collage
    _container.share_service.share(Mediaitem(media_type="collage", processed=Path("1.jpg")), 3)

    # check subprocess.run was not invoked
    assert mock_run.call_count == 2


@patch("subprocess.run")
def test_share_parameters_are_literal_arguments_and_keep_defaults(mock_run, _container: Container, tmp_path: Path):
    action = appconfig.share.actions[0]
    action.processing.share_command = 'send-mail "{filename}" "{mail}" {copies}'
    action.processing.parameters = [
        ShareProcessingParameters(key="mail", ui_type="input", default="default@example.org", valid_min="1", valid_max="128"),
        ShareProcessingParameters(key="copies", default="1", valid_min="1", valid_max="3"),
    ]
    parameters = {"mail": 'guest@example.org"; touch /tmp/not-created; #'}
    filename = tmp_path / "photo with spaces.jpg"

    _container.share_service.share(Mediaitem(media_type="image", processed=filename), 0, parameters)

    command = mock_run.call_args.args[0]
    assert command == [
        "send-mail",
        str(filename),
        parameters["mail"],
        "1",
    ]
    assert "shell" not in mock_run.call_args.kwargs
    assert parameters == {"mail": 'guest@example.org"; touch /tmp/not-created; #'}


@patch("subprocess.run")
def test_share_rejects_unconfigured_reserved_and_out_of_range_parameters(mock_run, _container: Container):
    action = appconfig.share.actions[0]
    action.processing.parameters = [
        ShareProcessingParameters(key="copies", default="1", valid_min="1", valid_max="3"),
        ShareProcessingParameters(key="mail", ui_type="input", default="test", valid_min="1", valid_max="128"),
    ]

    invalid_parameters: list[dict[str, str]] = [
        {"unknown": "value"},
        {"filename": "other.jpg"},
        {"copies": "4"},
        {"copies": "not-an-integer"},
        {"mail": "x" * 129},
    ]
    for parameters in invalid_parameters:
        with pytest.raises(ShareParameterError):
            _container.share_service.share(Mediaitem(media_type="image", processed=Path("1.jpg")), 0, parameters)

    mock_run.assert_not_called()


@patch("subprocess.run")
def test_share_command_failure_does_not_increment_quota(mock_run, _container: Container):
    action = appconfig.share.actions[0]
    mock_run.side_effect = subprocess.CalledProcessError(1, ["echo"], stderr=b"private command output")

    with pytest.raises(ShareCommandError, match="Share command failed"):
        _container.share_service.share(Mediaitem(media_type="image", processed=Path("1.jpg")), 0)

    with Session(engine) as session:
        assert session.get(ShareLimits, action.name) is None
