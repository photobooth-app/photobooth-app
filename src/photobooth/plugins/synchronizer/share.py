import logging
from abc import ABC, abstractmethod
from importlib import resources
from pathlib import Path
from urllib.parse import quote

from .config import (
    BackendConfig,
    FilesystemBackendConfig,
    FilesystemShareConfig,
    FtpBackendConfig,
    FtpShareConfig,
    NextcloudBackendConfig,
)
from .connectors.base import AbstractConnector

logger = logging.getLogger(__name__)


class AbstractMediashare(ABC):
    def __init__(self, backend_config: BackendConfig, connector: AbstractConnector):
        self._config = backend_config
        self._connector = connector

    @abstractmethod
    def mediaitem_link(self, remote_path: Path) -> str | None: ...

    def downloadportal_url(self) -> str | None:
        if isinstance(self._config.share, FtpShareConfig | FilesystemShareConfig) and self._config.share.downloadportal_autoupload:
            dlportal_raw_url = self._config.share.media_url
        else:
            dlportal_raw_url = self._config.share.downloadportal_url

        if dlportal_raw_url:
            return f"{dlportal_raw_url.rstrip('/')}/#/?url="
        else:
            return None

    def get_share_link(self, filepath_remote: Path) -> str | None:
        if not self._config.share.enable_share_link:
            logger.info("generating share links in synchronizer plugin is disabled for this backend")
            return None

        downloadportal_url = self.downloadportal_url()
        mediaitem_url = self.mediaitem_link(filepath_remote)

        # sanity check on media url
        if not mediaitem_url:
            logger.error("cannot share because there is no URL available for the media file provided by the connector")
            return None

        # sanity check on downloadportal url
        if self._config.share.use_downloadportal and not downloadportal_url:
            logger.error("cannot share because use of downloadportal is enabled but no URL available")
            return None

        if self._config.share.use_downloadportal and downloadportal_url:
            mediaitem_url_safe = quote(mediaitem_url, safe="")
            out = downloadportal_url + mediaitem_url_safe
        else:
            out = mediaitem_url

        logger.info(f"share link created for {filepath_remote}: {out}")

        return out

    def update_downloadportal(self):
        if isinstance(self._config.share, FtpShareConfig | FilesystemShareConfig) and self._config.share.downloadportal_autoupload:
            dlportal_source_path = Path(str(resources.files("web").joinpath("download", "index.html")))
            dlportal_remote_path = Path(dlportal_source_path.name)
            if not self._connector.get_remote_samefile(dlportal_source_path, dlportal_remote_path):
                logger.info("downloadportal autoupload is enabled and remote file outdated. Trying to upload the file now.")
                self._connector.do_upload(dlportal_source_path, dlportal_remote_path)
            else:
                logger.info("downloadportal autoupload is enabled but remote file up to date. Nothing to do.")


class FilesystemMediashare(AbstractMediashare):
    def mediaitem_link(self, remote_path: Path) -> str | None:
        if not self._config.share.media_url:
            logger.error("missing url for nextcloud mediaitem link")
            return None

        mediaitem_url = self._config.share.media_url.rstrip("/") + "/" + remote_path.as_posix()

        return mediaitem_url


class FtpMediashare(AbstractMediashare):
    def mediaitem_link(self, remote_path: Path) -> str | None:
        if not self._config.share.media_url:
            logger.error("missing url for nextcloud mediaitem link")
            return None

        mediaitem_url = self._config.share.media_url.rstrip("/") + "/" + remote_path.as_posix()
        return mediaitem_url


class NextcloudMediashare(AbstractMediashare):
    def mediaitem_link(self, remote_path: Path) -> str | None:
        nc_url = self._config.connector.url
        nc_shareid = self._config.share.share_id
        if not nc_url:
            logger.error("missing url for nextcloud mediaitem link")
            return None
        if not nc_shareid:
            logger.error("missing share_id for nextcloud mediaitem link")
            return None

        mediaitem_url = mediaitem_url = f"{nc_url.rstrip('/')}/public.php/dav/files/{nc_shareid}/" + remote_path.as_posix()

        return mediaitem_url


def share_factory(backend_config: BackendConfig, connector: AbstractConnector) -> AbstractMediashare:
    share_map: dict[type[BackendConfig], type[AbstractMediashare]] = {
        FilesystemBackendConfig: FilesystemMediashare,
        FtpBackendConfig: FtpMediashare,
        NextcloudBackendConfig: NextcloudMediashare,
    }
    ShareClass = share_map[type(backend_config)]
    return ShareClass(backend_config, connector)
