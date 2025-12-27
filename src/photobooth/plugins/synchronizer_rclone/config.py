from typing import Literal

from pydantic import BaseModel, Field, HttpUrl
from pydantic_settings import SettingsConfigDict

from ... import CONFIG_PATH
from ...services.config.baseconfig import BaseConfig


class Common(BaseModel):
    enabled: bool = Field(
        default=False,
        description="Enable plugin to sync media files globally.",
    )

    enable_share_links: bool = Field(
        default=True,
        description="Enable the share link generation for QR codes for this plugin.",
    )

    rclone_log_level: Literal["DEBUG", "INFO", "NOTICE", "ERROR"] = Field(
        default="NOTICE",
        description="Log verbosity of Rclone. The logfile is written to log/rclone.log.",
    )


class SyncConfig(BaseModel):
    enable_immediate_sync: bool = Field(
        default=True,
        description="Sync immediate when media is added/modified/deleted in the gallery. Enable this for QR code sharing.",
    )

    enable_regular_sync: bool = Field(
        default=True,
        description="Check media folder every X minutes and synchronize any missing files.",
    )
    interval: int = Field(
        default=1,
        description="Interval for full sync in minutes.",
    )


class ShareConfig(BaseModel):
    enable_share_link: bool = Field(
        default=True,
        description="Enable to generate a link displayed as QR code. You can have multiple QR codes, but it is recommended to enable only one.",
    )
    publiclink_override: HttpUrl | None = Field(
        default=None,
        description="Mediafiles copied to remote are accessible using this url. The filename is appended automatically when generating the qr code link.",
    )
    use_downloadportal: bool = Field(
        default=True,
        description="Using the download-portal improves the endusers' experience when downloading and sharing mediaitems. When enabled, the download-portal url needs to point to publicly available webspace. Some backends support automatic setup (autoupload), for others check the documentation.",
    )
    shareportal_url: HttpUrl | None = Field(
        default=None,
        description="Url used to build the links for QR codes pointing to the download portal (if enabled above).",
    )
    downloadportal_autoupload: bool = Field(
        default=True,
        description="Automatically copy the downloadportal file to the remote. You need to ensure that the media-url below is accessible publicly to use this function.",
    )


class RemoteConfig(BaseModel):
    enabled: bool = Field(default=False, description="Enable synchronization on this remote")
    description: str = Field(
        default="default description",
        description="",
    )
    name: str = Field(
        default="localremote",
        description="Name of the remote given during configuration.",
    )

    subdir: str = Field(
        default="subdir",
        description="subdir that is used as base to sync to.",
    )

    syncconfig: SyncConfig

    shareconfig: ShareConfig


class SynchronizerConfig(BaseConfig):
    model_config = SettingsConfigDict(
        title="Synchronizer and Share-Link Generation",
        json_file=f"{CONFIG_PATH}plugin_synchronizer_rclone.json",
        env_prefix="synchronizer_rclone-",
    )

    common: Common = Common()

    remotes: list[RemoteConfig] = [
        RemoteConfig(
            enabled=True,
            syncconfig=SyncConfig(),
            shareconfig=ShareConfig(),
        )
    ]
