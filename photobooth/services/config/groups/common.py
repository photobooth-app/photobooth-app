"""
AppConfig class providing central config

"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class GroupCommon(BaseModel):
    """Common config for photobooth."""

    model_config = ConfigDict(title="Common Config")

    countdown_capture_first: float = Field(
        default=2.0,
        multiple_of=0.1,
        ge=0,
        le=20,
        description="Countdown in seconds, started when user start a capture process",
    )

    countdown_capture_second_following: float = Field(
        default=1.0,
        multiple_of=0.1,
        ge=0,
        le=20,
        description="Countdown in seconds, used for second and following captures for collages",
    )
    countdown_camera_capture_offset: float = Field(
        default=0.2,
        multiple_of=0.05,
        ge=0,
        le=20,
        description="Trigger camera capture by offset earlier (in seconds). 0 trigger exactly when countdown is 0. Use to compensate for delay in camera processing for better UX.",
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
