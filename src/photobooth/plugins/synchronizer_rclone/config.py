from platform import node
from typing import Literal

from pydantic import BaseModel, Field
from pydantic_settings import SettingsConfigDict

from ... import CONFIG_PATH
from ...services.config.baseconfig import BaseConfig

hostname = node() if node() != "" else "localhost"


class Common(BaseModel):
    enabled: bool = Field(
        default=False,
        description="Enable plugin to sync media files globally.",
    )

    full_sync_interval: int = Field(
        default=5,
        description="Interval for full sync in minutes.",
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
    rclone_enable_logging: bool = Field(
        default=True,
        description="Enable logging to log/rclone.log.",
    )
    rclone_log_level: Literal["DEBUG", "INFO", "NOTICE", "ERROR"] = Field(
        default="NOTICE",
        description="Log verbosity.",
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

    manual_public_link: str | None = Field(  # str instead HttpUrl because otherwise {}-placeholder would be encoded by pydantic
        default=None,
        description="If given, mediafiles copied to the remote must be accessible using this URL. Use {filename} to replace for the actual filename. If empty, Rclone tries to generate a public link (limited to S3 and maybe others).",
    )

    use_sharepage: bool = Field(
        default=True,
        description="Using the sharepage improves the endusers' experience when viewing mediaitems after scanning the QR code. When enabled, the sharepage URL needs to point to a public webspace, https is preferred for full functionality.",
    )
    sharepage_url: str | None = Field(
        default=None,
        description="URL used to build the links for QR codes pointing to the sharepage (if enabled above).",
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
        default="",
        description="Name of the remote given during configuration including the ':' at the end. You need to setup the remote separately using the rclone web-ui at http://localhost:5572/. To sync to local folders set '/' (Linux) or 'C:\\' (Windows) and use subdir as target.",
        json_schema_extra={"list_api": "/api/admin/enumerate/rclone_remotes"},
    )
    subdir: str = Field(
        default="",
        description="Subdir that is used as base to sync to. In this directory the sharepage (subdir/index.html) and mediafiles (subdir/media/) will be placed. WARNING: This directory is owned by the app - it will delete unknown files!",
    )

    enable_immediate_sync: bool = Field(
        default=True,
        description="Sync immediate when media is added/modified/deleted in the gallery. Enable this for QR code sharing.",
    )
    enable_regular_sync: bool = Field(
        default=True,
        description="Check media folder every X minutes and synchronize any missing files.",
    )
    enable_sharepage_sync: bool = Field(
        default=True,
        description="Copy the sharepage-file (index.html) to the remote on startup.",
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
            enabled=False,
            description="demo localremote",
            name="/",
            subdir="tmp/localsync",
            shareconfig=ShareConfig(),
        )
    ]
