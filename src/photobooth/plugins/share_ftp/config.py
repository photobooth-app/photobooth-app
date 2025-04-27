from pydantic import Field
from pydantic_settings import SettingsConfigDict

from photobooth import CONFIG_PATH
from photobooth.services.config.baseconfig import BaseConfig


class ShareFtpConfig(BaseConfig):
    model_config = SettingsConfigDict(
        title="Share FTP Plugin Config",
        json_file=f"{CONFIG_PATH}plugin_shareftp.json",
        env_prefix="shareftp-",
    )

    shareftp_enabled: bool = Field(
        default=False,
        description="Enable integration to sync photos.",
    )
    ftp_host: str = Field(
        default="",
    )
    ftp_username: str = Field(
        default="",
    )
    ftp_password: str = Field(
        default="",
    )
    ftp_remote_dir: str = Field(
        default="/",
    )
    share_url: str = Field(
        default="http://test.de/{filename}",
    )
