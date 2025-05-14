from pydantic import BaseModel, ConfigDict, Field, SecretStr, SerializationInfo, field_serializer
from pydantic_settings import SettingsConfigDict

from photobooth import CONFIG_PATH
from photobooth.services.config.baseconfig import BaseConfig
from photobooth.services.config.serializer import contextual_serializer_password


class Common(BaseConfig):
    enabled: bool = Field(
        default=False,
        description="Enable integration to sync media files.",
    )

    share_url: str = Field(
        default="",
    )

    media_url: str = Field(
        default="/{filename}",
    )


class FtpServerConfigGroup(BaseConfig):
    host: str = Field(
        default="",
    )
    port: int = Field(
        default=21,
    )
    username: str = Field(
        default="",
    )
    password: SecretStr = Field(
        default=SecretStr(""),
    )
    secure: bool = Field(
        default=True,
    )

    # reveal password in admin backend.
    @field_serializer("password")
    def contextual_serializer(self, value, info: SerializationInfo):
        return contextual_serializer_password(value, info)


class FilesystemConfigGroup(BaseConfig):
    target_dir: str = Field(
        default="./tmp/test123",
    )


class Backends(BaseModel):
    model_config = ConfigDict(title="Sync Backend Configuration")

    enabled: bool = Field(
        default=True,
        description="Enable synchronization on this backend",
    )

    ftp_server: FtpServerConfigGroup = FtpServerConfigGroup()
    filesystem: FilesystemConfigGroup = FilesystemConfigGroup()


class SynchronizerConfig(BaseConfig):
    model_config = SettingsConfigDict(
        title="Share FTP Plugin Config",
        json_file=f"{CONFIG_PATH}plugin_shareftp.json",
        env_prefix="shareftp-",
    )

    common: Common = Common()
    backends: list[Backends] = [Backends()]

    ftp_server: FtpServerConfigGroup = FtpServerConfigGroup()
    filesystem: FilesystemConfigGroup = FilesystemConfigGroup()
