from pathlib import Path
from typing import Literal

from pydantic import BaseModel, DirectoryPath, Field, SecretStr, SerializationInfo, field_serializer
from pydantic_settings import SettingsConfigDict

from photobooth import CONFIG_PATH
from photobooth.services.config.baseconfig import BaseConfig
from photobooth.services.config.serializer import contextual_serializer_password


class Common(BaseConfig):
    enabled: bool = Field(default=False, description="Enable integration to sync media files.")

    enable_share_link: bool = Field(default=True)
    share_url: str = Field(default="")
    media_url: str = Field(default="/{filename}")


class FtpServerBackendConfig(BaseConfig):
    model_config = SettingsConfigDict(title="FTP Server")

    backend_type: Literal["ftp"] = "ftp"

    host: str = Field(default="")
    port: int = Field(default=21)
    username: str = Field(default="")
    password: SecretStr = Field(default=SecretStr(""))
    secure: bool = Field(default=True)

    # reveal password in admin backend.
    @field_serializer("password")
    def contextual_serializer(self, value, info: SerializationInfo):
        return contextual_serializer_password(value, info)


class FilesystemBackendConfig(BaseConfig):
    model_config = SettingsConfigDict(title="Filesystem")

    backend_type: Literal["filesystem"] = "filesystem"

    target_dir: DirectoryPath | None = Field(default=None)

class NextcloudBackendConfig(BaseConfig):
    model_config = SettingsConfigDict(title="NextCloud")

    backend_type: Literal["nextcloud"] = "nextcloud"

    url: str = Field(default="")
    username: str = Field(default="")
    password: SecretStr = Field(default=SecretStr(""))

    # Remote directory
    target_dir: str = Field(default="")


class Backend(BaseModel):
    enabled: bool = Field(default=False, description="Enable synchronization on this backend")

    description: str = Field(default="backend default name")

    backend_config: FtpServerBackendConfig | FilesystemBackendConfig | NextcloudBackendConfig = Field(discriminator="backend_type")


class SynchronizerConfig(BaseConfig):
    model_config = SettingsConfigDict(
        title="Synchronizer Plugin Config",
        json_file=f"{CONFIG_PATH}plugin_synchronizer.json",
        env_prefix="synchronizer-",
    )

    common: Common = Common()
    backends: list[Backend] = [Backend(enabled=True, description="demo tmp sync", backend_config=FilesystemBackendConfig(target_dir=Path("./tmp")))]
