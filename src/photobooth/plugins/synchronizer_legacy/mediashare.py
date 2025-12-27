import logging
from abc import ABC, abstractmethod
from importlib import resources
from pathlib import Path
from typing import Generic, TypeVar
from urllib.parse import quote

from .config import (
    BackendConfig,
    FilesystemBackendConfig,
    FilesystemShareConfig,
    FtpBackendConfig,
    FtpShareConfig,
    NextcloudBackendConfig,
)
from .connectors.abstractconnector import AbstractConnector

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BackendConfig)


class AbstractMediashare(ABC, Generic[T]):
    def __init__(self, backend_config: T, connector: AbstractConnector):
        self._config: T = backend_config
        self._connector = connector

    def __str__(self):
        return f"{self.__class__.__name__} ({self._connector})"

    @abstractmethod
    def mediaitem_link(self, remote_path: Path) -> str | None: ...

    @staticmethod
    def _build_mediaitem_url(base_url: str, remote_path: Path) -> str:
        return base_url.rstrip("/") + "/" + remote_path.as_posix()

    def downloadportal_url(self) -> str | None:
        if isinstance(self._config.share, FtpShareConfig | FilesystemShareConfig) and self._config.share.downloadportal_autoupload:
            dlportal_raw_url = self._config.share.media_url
        else:
            dlportal_raw_url = self._config.share.downloadportal_url

        if dlportal_raw_url:
            return f"{str(dlportal_raw_url).rstrip('/')}/#/?url="
        else:
            return None

    def get_share_link(self, filepath_remote: Path) -> str | None:
        downloadportal_url = self.downloadportal_url()
        mediaitem_url = self.mediaitem_link(filepath_remote)

        # sanity check on media url
        if not mediaitem_url:
            logger.error(f"cannot share because there is no URL available for the media file provided by the connector {self._connector}")
            return None

        # sanity check on downloadportal url
        if self._config.share.use_downloadportal and not downloadportal_url:
            logger.error(f"cannot share because use of downloadportal is enabled but no URL available for {self._connector}")
            return None

        if self._config.share.use_downloadportal and downloadportal_url:
            mediaitem_url_safe = quote(mediaitem_url, safe="")
            out = downloadportal_url + mediaitem_url_safe
        else:
            out = mediaitem_url

        logger.info(f"share link created for {filepath_remote}: {out}")

        return out

    def downloadportal_file(self) -> Path | None:
        if isinstance(self._config.share, FtpShareConfig | FilesystemShareConfig) and self._config.share.downloadportal_autoupload:
            dlportal_source_path = Path(str(resources.files("web").joinpath("download/index.html")))
            assert dlportal_source_path.is_file()

            return dlportal_source_path
        else:
            return None


class FilesystemMediashare(AbstractMediashare[FilesystemBackendConfig]):
    def mediaitem_link(self, remote_path: Path) -> str | None:
        if not self._config.share.media_url:
            logger.error(f"missing url for {self} mediaitem link")
            return None

        mediaitem_url = self._build_mediaitem_url(str(self._config.share.media_url), remote_path)

        return mediaitem_url


class FtpMediashare(AbstractMediashare[FtpBackendConfig]):
    def mediaitem_link(self, remote_path: Path) -> str | None:
        if not self._config.share.media_url:
            logger.error(f"missing url for {self} mediaitem link")
            return None

        mediaitem_url = self._build_mediaitem_url(str(self._config.share.media_url), remote_path)

        return mediaitem_url


class NextcloudMediashare(AbstractMediashare[NextcloudBackendConfig]):
    def mediaitem_link(self, remote_path: Path) -> str | None:
        nc_url = self._config.connector.url
        nc_shareid = self._config.share.share_id
        if not nc_url:
            logger.error(f"missing url for {self} mediaitem link")
            return None
        if not nc_shareid:
            logger.error(f"missing share_id for {self} mediaitem link")
            return None

        mediaitem_url = self._build_mediaitem_url(f"{str(nc_url).rstrip('/')}/public.php/dav/files/{nc_shareid}/", remote_path)

        return mediaitem_url


def share_factory(backend_config: BackendConfig, connector: AbstractConnector) -> AbstractMediashare:
    share_map: dict[type[BackendConfig], type[AbstractMediashare]] = {
        FilesystemBackendConfig: FilesystemMediashare,
        FtpBackendConfig: FtpMediashare,
        NextcloudBackendConfig: NextcloudMediashare,
    }
    ShareClass = share_map[type(backend_config)]
    return ShareClass(backend_config, connector)
