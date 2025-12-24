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


class SyncFullConfig(BaseModel):
    enable_regular_sync: bool = Field(
        default=True,
        description="Check media folder every 5 minutes and upload any missing files",
    )
    interval: int = Field(
        default=1,
        description="",
    )


class SyncQueueConfig(BaseModel):
    enable_immediate_sync: bool = Field(
        default=True,
        description="Sync immediate when media is added/modified/deleted in the gallery. Enable this for QR code sharing.",
    )


class ShareConfig(BaseModel):
    enable_share_link: bool = Field(
        default=True,
        description="Enable to generate a link displayed as QR code. You can have multiple QR codes, but it is recommended to enable only one.",
    )
    use_downloadportal: bool = Field(
        default=True,
        description="Using the download-portal improves the endusers' experience when downloading and sharing mediaitems. When enabled, the download-portal url needs to point to publicly available webspace. Some backends support automatic setup (autoupload), for others check the documentation.",
    )
    downloadportal_url: HttpUrl | None = Field(
        default=None,
        description="Url used to build the links for QR codes pointing to the download portal (if enabled above).",
    )
    downloadportal_autoupload: bool = Field(
        default=True,
        description="Automatically copy the downloadportal file to the remote. You need to ensure that the media-url below is accessible publicly to use this function.",
    )
    custom_share_url: HttpUrl | None = Field(
        default=None,
        description="Mediafiles copied to remote are accessible using this url. The filename is appended automatically when generating the qr code link.",
    )


class RcloneRemoteConfig(BaseModel):
    remote: str = Field(
        default="localremote",
        description="Name of the remote given during configuration.",
    )

    remote_base_dir: str = Field(
        default="subdir",
        description="subdir that is used as base to sync to.",
    )


class cfgGroup(BaseModel):
    enabled: bool = Field(default=False, description="Enable synchronization on this remote")
    description: str = Field(
        default="default description",
        description="",
    )
    rcloneRemoteConfig: RcloneRemoteConfig
    syncqueueconfig: SyncQueueConfig
    syncfullconfig: SyncFullConfig
    shareconfig: ShareConfig


class SynchronizerConfig(BaseConfig):
    model_config = SettingsConfigDict(
        title="Synchronizer and Share-Link Generation",
        json_file=f"{CONFIG_PATH}plugin_synchronizer.json",
        env_prefix="synchronizer-",
    )

    common: Common = Common()
    remotes: list[cfgGroup] = [
        cfgGroup(
            enabled=True,
            rcloneRemoteConfig=RcloneRemoteConfig(),
            syncqueueconfig=SyncQueueConfig(),
            syncfullconfig=SyncFullConfig(),
            shareconfig=ShareConfig(),
        )
    ]
