from platform import node
from typing import Literal

from pydantic import BaseModel, Field, HttpUrl
from pydantic_settings import SettingsConfigDict

from ... import CONFIG_PATH
from ...services.config.baseconfig import BaseConfig

hostname = node() if node() != "" else "localhost"


class Common(BaseModel):
    enabled: bool = Field(
        default=False,
        description="Enable plugin to sync media files globally.",
    )

    enabled_share_links: bool = Field(
        default=True,
        description="Global switch to enable the share link generation for QR codes in this plugin.",
    )

    enabled_custom_qr_url: bool = Field(
        default=False,
        description="If you have your own solution/custom setup (local hotspot, ...), enable this option and the cusotm qr url is displayed as QR code in the frontend.",
    )
    custom_qr_url: str = Field(
        default=f"http://{hostname}:8000/sharepage/#?url=http://{hostname}:8000/media/full/{{identifier}}",
        description="URL displayed as QR code to image for download. Need you to sync the files on your own or allow the user to access via hotspot. {identifier} is replaced by the actual item's id, {filename} is replaced by the actual filename on the photobooth-data, in QR code.",
    )


class RcloneClientConfig(BaseModel):
    model_config = SettingsConfigDict(
        title="Global Rclone Instance Settings",
    )

    rclone_log_level: Literal["DEBUG", "INFO", "NOTICE", "ERROR"] = Field(
        default="NOTICE",
        description="Log verbosity of Rclone. The logfile is written to log/rclone.log.",
    )

    rclone_transfers: int = Field(
        default=4,
        ge=1,
        le=8,
        description="Maximum number of concurrent transfers. Ensure your servers handles the amount of simultaneous connections including the connections for the checkers.",
    )

    rclone_checkers: int = Field(
        default=4,
        ge=1,
        le=8,
        description="Maximum number of concurrent checkers. Ensure your servers handles the amount of simultaneous connections including the connections for the transfers.",
    )

    enable_webui: bool = Field(
        default=True,
        description="Enable the web interface of rclone. It will be accessible from the device running the app only for security reasons. http://localhost:5572",
    )


class ShareConfig(BaseModel):
    enabled: bool = Field(
        default=False,
        description="Enable to generate a link displayed as QR code. You can have multiple QR codes, but it is recommended to enable only one.",
    )

    publiclink_override: HttpUrl | None = Field(
        default=None,
        description="Mediafiles copied to remote are accessible using this url. The filename is appended automatically when generating the qr code link.",
    )
    use_sharepage: bool = Field(
        default=True,
        description="Using the download-portal improves the endusers' experience when downloading and sharing mediaitems. When enabled, the download-portal url needs to point to publicly available webspace. Some backends support automatic setup (autoupload), for others check the documentation.",
    )
    sharepage_url: HttpUrl | None = Field(
        default=None,
        description="Url used to build the links for QR codes pointing to the download portal (if enabled above).",
    )
    sharepage_autosync: bool = Field(
        default=True,
        description="Automatically copy the sharepage-file to the remote. You need to ensure that the media-url below is accessible publicly to use this function.",
    )


class RemoteConfig(BaseModel):
    enabled: bool = Field(
        default=False,
        description="Enable synchronization on this remote",
    )
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

    shareconfig: ShareConfig


class SynchronizerConfig(BaseConfig):
    model_config = SettingsConfigDict(
        title="Synchronizer and Share-Link Generation",
        json_file=f"{CONFIG_PATH}plugin_synchronizer_rclone.json",
        env_prefix="synchronizer_rclone-",
    )

    common: Common = Common()

    rclone_client_config: RcloneClientConfig = RcloneClientConfig()

    remotes: list[RemoteConfig] = [
        RemoteConfig(
            enabled=True,
            shareconfig=ShareConfig(),
        )
    ]
