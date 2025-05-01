from pydantic import Field, SecretStr, SerializationInfo, field_serializer
from pydantic_settings import SettingsConfigDict

from photobooth import CONFIG_PATH
from photobooth.services.config.baseconfig import BaseConfig


class Common(BaseConfig):
    enabled: bool = Field(
        default=False,
        description="Enable integration to sync media files.",
    )

    share_url: str = Field(
        default="http://test.de/{filename}",
    )


class FtpServer(BaseConfig):
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
    root_dir: str = Field(
        default="/",
    )

    # reveal password in admin backend.
    @field_serializer("password")
    def contextual_serializer(self, value, info: SerializationInfo):
        if info.context:
            if info.context.get("secrets_is_allowed", False):
                return value.get_secret_value()

        return "************"


class ShareFtpConfig(BaseConfig):
    model_config = SettingsConfigDict(
        title="Share FTP Plugin Config",
        json_file=f"{CONFIG_PATH}plugin_shareftp.json",
        env_prefix="shareftp-",
    )

    common: Common = Common()
    ftp_server: FtpServer = FtpServer()
