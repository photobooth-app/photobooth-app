from pathlib import Path
from typing import Literal

from pydantic import BaseModel, DirectoryPath, Field, HttpUrl, SecretStr, SerializationInfo, field_serializer
from pydantic_settings import SettingsConfigDict

from ... import CONFIG_PATH
from ...services.config.baseconfig import BaseConfig
from ...services.config.serializer import contextual_serializer_password


class Common(BaseModel):
    enabled: bool = Field(
        default=False,
        description="Enable plugin to sync media files globally.",
    )

    enable_share_links: bool = Field(
        default=True,
        description="Enable the share link generation for QR codes for this plugin.",
    )


class BaseConnectorConfig(BaseModel): ...


class FtpConnectorConfig(BaseConnectorConfig):
    host: str = Field(
        # default="",
        description="Hostname/IP of the FTP server to connect to.",
    )
    port: int = Field(
        default=21,
        description="FTP Server port, usually 21.",
    )
    username: str = Field(
        default="",
        description="Login username",
    )
    password: SecretStr = Field(
        default=SecretStr(""),
        description="Login password. Please note, the password is stored in clear text in the config.",
    )
    secure: bool = Field(
        default=True,
        description="Try to encrypt FTP connection using TLS/SSL. Disable if login fails.",
    )
    idle_timeout: int = Field(
        default=30,
        description="After timeout, the connections to the server are closed. The connection is automatically established, when needed again.",
    )

    # reveal password in admin backend.
    @field_serializer("password")
    def contextual_serializer(self, value, info: SerializationInfo):
        return contextual_serializer_password(value, info)


class FilesystemConnectorConfig(BaseConnectorConfig):
    target_dir: DirectoryPath = Field(
        # default=DirectoryPath(),
        description="Directory to synchronize to.",
    )


class NextcloudConnectorConfig(BaseConnectorConfig):
    url: HttpUrl = Field(
        # default=HttpUrl(""),
        description="Url to the Nextcloud instance.",
    )
    username: str = Field(
        default="",
        description="Username to login to Nextcloud.",
    )
    password: SecretStr = Field(
        default=SecretStr(""),
        description="Password to login to Nextcloud. Please note, the password is stored in clear text in the config.",
    )

    # Remote directory
    target_dir: str = Field(
        default="",
        description="Directory to synchronize to.",
    )

    # reveal password in admin backend.
    @field_serializer("password")
    def contextual_serializer(self, value, info: SerializationInfo):
        return contextual_serializer_password(value, info)


class BaseShareConfig(BaseModel):
    use_downloadportal: bool = Field(
        default=True,
        description="Using the download-portal improves the endusers' experience when downloading and sharing mediaitems. When enabled, the download-portal url needs to point to publicly available webspace. Some backends support automatic setup (autoupload), for others check the documentation.",
    )
    downloadportal_url: HttpUrl | None = Field(
        default=None,
        description="Url used to build the links for QR codes pointing to the download portal (if enabled above).",
    )


class FilesystemShareConfig(BaseShareConfig):
    downloadportal_autoupload: bool = Field(
        default=True,
        description="Automatically copy the downloadportal file to the remote. You need to ensure that the media-url below is accessible publicly to use this function.",
    )

    media_url: HttpUrl | None = Field(
        default=None,
        description="Mediafiles copied to remote are accessible using this url. The filename is appended automatically when generating the qr code link.",
    )


class FtpShareConfig(BaseShareConfig):
    downloadportal_autoupload: bool = Field(
        default=True,
        description="Automatically copy the downloadportal file to the remote. You need to ensure that the media-url below is accessible publicly to use this function.",
    )

    media_url: HttpUrl | None = Field(
        default=None,
        description="Mediafiles copied to remote are accessible using this url. The filename is appended automatically when generating the qr code link.",
    )


class NextcloudShareConfig(BaseShareConfig):
    share_id: str = Field(
        default="",
        description="Insert the share-id generated for public links in Nextcloud.",
    )


class BaseBackendConfig(BaseModel): ...


class FtpBackendConfig(BaseBackendConfig):
    model_config = SettingsConfigDict(title="FTP Server")

    backend_type: Literal["ftp"] = "ftp"

    connector: FtpConnectorConfig
    share: FtpShareConfig


class FilesystemBackendConfig(BaseBackendConfig):
    model_config = SettingsConfigDict(title="Filesystem")

    backend_type: Literal["filesystem"] = "filesystem"

    connector: FilesystemConnectorConfig
    share: FilesystemShareConfig


class NextcloudBackendConfig(BaseBackendConfig):
    model_config = SettingsConfigDict(title="NextCloud")

    backend_type: Literal["nextcloud"] = "nextcloud"

    connector: NextcloudConnectorConfig
    share: NextcloudShareConfig


BackendConfig = FilesystemBackendConfig | FtpBackendConfig | NextcloudBackendConfig
ConnectorConfig = FilesystemConnectorConfig | FtpConnectorConfig | NextcloudConnectorConfig
ShareConfig = FilesystemShareConfig | FtpShareConfig | NextcloudShareConfig


class Backend(BaseModel):
    enabled: bool = Field(default=False, description="Enable synchronization on this backend")

    description: str = Field(default="backend default name")

    enable_regular_sync: bool = Field(default=True, description="Check media folder every 5 minutes and upload any missing files")
    enable_immediate_sync: bool = Field(
        default=True,
        description="Sync immediate when media is added/modified/deleted in the gallery. Enable this for QR code sharing.",
    )
    enable_share_link: bool = Field(
        default=True,
        description="Enable to generate a link displayed as QR code. You can have multiple QR codes, but it is recommended to enable only one.",
    )

    backend_config: BackendConfig = Field(discriminator="backend_type")


class SynchronizerConfig(BaseConfig):
    model_config = SettingsConfigDict(
        title="Synchronizer and Share-Link Generation",
        json_file=f"{CONFIG_PATH}plugin_synchronizer.json",
        env_prefix="synchronizer-",
    )

    common: Common = Common()
    backends: list[Backend] = [
        Backend(
            enabled=True,
            description="demo tmp sync",
            backend_config=FilesystemBackendConfig(
                connector=FilesystemConnectorConfig(
                    target_dir=Path("./tmp"),
                ),
                share=FilesystemShareConfig(
                    use_downloadportal=False,
                    downloadportal_autoupload=False,
                ),
            ),
        )
    ]
