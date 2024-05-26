"""
AppConfig class providing central config

"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class GroupCommon(BaseModel):
    """Common config for photobooth."""

    model_config = ConfigDict(title="Common Config")

    admin_password: str = Field(
        default="0000",
        description="Password to access the admin dashboard.",
    )

    logging_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = Field(
        default="DEBUG",
        description="Log verbosity. File is writte to disc, and latest log is displayed also in UI.",
    )

    webserver_bind_ip: str = Field(
        default="0.0.0.0",
        description="IP/Hostname to bind the webserver to. 0.0.0.0 means bind to all IP adresses of host.",
    )
    webserver_port: int = Field(
        default=8000,
        description="Port to serve the photobooth website. Ensure the port is available. Ports below 1024 need root!",
    )

    users_delete_to_recycle_dir: bool = Field(
        default=True,
        description="If enabled, the captured files are moved to the recycle directory instead permanently deleted. Accidentally deleted images can be restored by the admin manually. Please inform users about the fact that no capture is deleted, if you enable the function!",
    )
