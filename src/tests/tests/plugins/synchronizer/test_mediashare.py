import logging
from pathlib import Path
from unittest.mock import Mock

import pytest
from pydantic import HttpUrl

from photobooth.plugins.synchronizer.config import (
    FilesystemBackendConfig,
    FilesystemConnectorConfig,
    FilesystemShareConfig,
    FtpBackendConfig,
    FtpConnectorConfig,
    FtpShareConfig,
    NextcloudBackendConfig,
    NextcloudConnectorConfig,
    NextcloudShareConfig,
)
from photobooth.plugins.synchronizer.connectors.abstractconnector import AbstractConnector
from photobooth.plugins.synchronizer.mediashare import (
    FilesystemMediashare,
    FtpMediashare,
    NextcloudMediashare,
    share_factory,
)

logger = logging.getLogger(name=None)


@pytest.fixture
def mock_connector():
    return Mock(spec=AbstractConnector)


def test_get_str(mock_connector):
    cfg = FilesystemBackendConfig(
        share=FilesystemShareConfig(media_url=HttpUrl("http://example.com/media")),
        connector=FilesystemConnectorConfig(
            target_dir=Path("./tmp/"),
        ),
    )
    share = FilesystemMediashare(cfg, mock_connector)

    assert share.__str__()


def test_filesystem_mediaitem_link(mock_connector):
    cfg = FilesystemBackendConfig(
        share=FilesystemShareConfig(media_url=HttpUrl("http://example.com/media")),
        connector=FilesystemConnectorConfig(
            target_dir=Path("./tmp/"),
        ),
    )
    share = FilesystemMediashare(cfg, mock_connector)

    expected = "http://example.com/media/some/media/file.mp4"
    assert share.mediaitem_link(Path("some/media/file.mp4")) == expected


def test_ftp_mediaitem_link(mock_connector):
    cfg = FtpBackendConfig(
        share=FtpShareConfig(media_url=HttpUrl("http://media.server/files")),
        connector=FtpConnectorConfig(host=""),
    )
    share = FtpMediashare(cfg, mock_connector)

    expected = "http://media.server/files/some/media/file.mp4"
    assert share.mediaitem_link(Path("some/media/file.mp4")) == expected


def test_nextcloud_mediaitem_link(mock_connector):
    cfg = NextcloudBackendConfig(
        connector=NextcloudConnectorConfig(url=HttpUrl("https://nextcloud.local")),
        share=NextcloudShareConfig(share_id="SHARE123"),
    )
    share = NextcloudMediashare(cfg, mock_connector)

    expected = "https://nextcloud.local/public.php/dav/files/SHARE123/some/media/file.mp4"
    assert share.mediaitem_link(Path("some/media/file.mp4")) == expected


def test_get_share_link_direct(mock_connector):
    cfg = FilesystemBackendConfig(
        share=FilesystemShareConfig(media_url=HttpUrl("http://example.com"), use_downloadportal=False),
        connector=FilesystemConnectorConfig(
            target_dir=Path("./tmp/"),
        ),
    )
    share = FilesystemMediashare(cfg, mock_connector)

    expected = "http://example.com/some/media/file.mp4"
    assert share.get_share_link(Path("some/media/file.mp4")) == expected


def test_get_share_link_downloadportal(mock_connector):
    cfg = FilesystemBackendConfig(
        share=FilesystemShareConfig(
            media_url=HttpUrl("http://example.com"),
            use_downloadportal=True,
            downloadportal_autoupload=False,
            downloadportal_url=HttpUrl("https://dlportal.local"),
        ),
        connector=FilesystemConnectorConfig(
            target_dir=Path("./tmp/"),
        ),
    )
    share = FilesystemMediashare(cfg, mock_connector)

    result = share.get_share_link(Path("some/media/file.mp4"))
    assert result == "https://dlportal.local/#/?url=http%3A%2F%2Fexample.com%2Fsome%2Fmedia%2Ffile.mp4"


def test_downloadportal_url_autoupload_enabled(mock_connector):
    cfg = FilesystemBackendConfig(
        share=FilesystemShareConfig(
            media_url=HttpUrl("http://example.com/media"),
            downloadportal_autoupload=True,
        ),
        connector=FilesystemConnectorConfig(
            target_dir=Path("./tmp/"),
        ),
    )
    share = FilesystemMediashare(cfg, mock_connector)

    assert share.downloadportal_url() == "http://example.com/media/#/?url="
    # downloadportal_url is ignored in case autoupload.


def test_update_downloadportal_upload_triggered(mock_connector):
    mock_connector.get_remote_samefile.return_value = False

    cfg = FilesystemBackendConfig(
        share=FilesystemShareConfig(
            media_url=HttpUrl("http://example.com"),
            downloadportal_autoupload=True,
        ),
        connector=FilesystemConnectorConfig(
            target_dir=Path("./tmp/"),
        ),
    )
    share = FilesystemMediashare(cfg, mock_connector)
    share.update_downloadportal()

    mock_connector.do_upload.assert_called_once()


def test_update_downloadportal_skipped_when_same(mock_connector):
    mock_connector.get_remote_samefile.return_value = True

    cfg = FilesystemBackendConfig(
        share=FilesystemShareConfig(
            media_url=HttpUrl("http://example.com"),
            downloadportal_autoupload=True,
        ),
        connector=FilesystemConnectorConfig(
            target_dir=Path("./tmp/"),
        ),
    )
    share = FilesystemMediashare(cfg, mock_connector)
    share.update_downloadportal()

    mock_connector.do_upload.assert_not_called()


def test_share_factory_returns_correct_type(mock_connector):
    fs_config = FilesystemBackendConfig(
        share=FilesystemShareConfig(
            media_url=HttpUrl("http://example.com"),
        ),
        connector=FilesystemConnectorConfig(
            target_dir=Path("./tmp/"),
        ),
    )
    ftp_config = FtpBackendConfig(
        share=FtpShareConfig(media_url=HttpUrl("http://server")),
        connector=FtpConnectorConfig(host=""),
    )
    nc_config = NextcloudBackendConfig(
        connector=NextcloudConnectorConfig(url=HttpUrl("http://url")),
        share=NextcloudShareConfig(share_id="id"),
    )

    assert isinstance(share_factory(fs_config, mock_connector), FilesystemMediashare)
    assert isinstance(share_factory(ftp_config, mock_connector), FtpMediashare)
    assert isinstance(share_factory(nc_config, mock_connector), NextcloudMediashare)
