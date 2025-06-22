from pathlib import Path
from typing import Literal

from pydantic import BaseModel, DirectoryPath, Field, SecretStr, SerializationInfo, field_serializer
from pydantic_settings import SettingsConfigDict

from photobooth import CONFIG_PATH
from photobooth.services.config.baseconfig import BaseConfig
from photobooth.services.config.serializer import contextual_serializer_password


class Common(BaseModel):
    enabled: bool = Field(default=False, description="Enable plugin to sync media files globally.")

    enable_share_links: bool = Field(default=True)


class BaseConnectorConfig(BaseModel): ...


class FtpConnectorConfig(BaseConnectorConfig):
    host: str = Field(default="")
    port: int = Field(default=21)
    username: str = Field(default="")
    password: SecretStr = Field(default=SecretStr(""))
    secure: bool = Field(default=True)
    idle_timeout: int = Field(default=30)

    # reveal password in admin backend.
    @field_serializer("password")
    def contextual_serializer(self, value, info: SerializationInfo):
        return contextual_serializer_password(value, info)


class FilesystemConnectorConfig(BaseConnectorConfig):
    target_dir: DirectoryPath | None = Field(default=None)


class NextcloudConnectorConfig(BaseConnectorConfig):
    url: str = Field(default="")
    username: str = Field(default="")
    password: SecretStr = Field(default=SecretStr(""))

    # Remote directory
    target_dir: str = Field(default="")

    # reveal password in admin backend.
    @field_serializer("password")
    def contextual_serializer(self, value, info: SerializationInfo):
        return contextual_serializer_password(value, info)


class BaseShareConfig(BaseModel):
    use_downloadportal: bool = Field(default=True)
    downloadportal_url: str = Field(default="")


class FilesystemShareConfig(BaseShareConfig):
    downloadportal_autoupload: bool = Field(default=True)

    media_url: str = Field(default="")


class FtpShareConfig(BaseShareConfig):
    downloadportal_autoupload: bool = Field(default=True)

    media_url: str = Field(default="")


class NextcloudShareConfig(BaseShareConfig):
    share_id: str = Field(default="")


class BaseBackendConfig(BaseModel): ...


class FtpBackendConfig(BaseBackendConfig):
    model_config = SettingsConfigDict(title="FTP Server")

    backend_type: Literal["ftp"] = "ftp"

    connector: FtpConnectorConfig = FtpConnectorConfig()
    share: FtpShareConfig = FtpShareConfig()


class FilesystemBackendConfig(BaseBackendConfig):
    model_config = SettingsConfigDict(title="Filesystem")

    backend_type: Literal["filesystem"] = "filesystem"

    connector: FilesystemConnectorConfig = FilesystemConnectorConfig()
    share: FilesystemShareConfig = FilesystemShareConfig()


class NextcloudBackendConfig(BaseBackendConfig):
    model_config = SettingsConfigDict(title="NextCloud")

    backend_type: Literal["nextcloud"] = "nextcloud"

    connector: NextcloudConnectorConfig = NextcloudConnectorConfig()
    share: NextcloudShareConfig = NextcloudShareConfig()


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
        title="Synchronizer Plugin Config",
        json_file=f"{CONFIG_PATH}plugin_synchronizer.json",
        env_prefix="synchronizer-",
    )

    common: Common = Common()
    backends: list[Backend] = [
        Backend(
            enabled=True,
            description="demo tmp sync",
            backend_config=FilesystemBackendConfig(connector=FilesystemConnectorConfig(target_dir=Path("./tmp"))),
        )
    ]
