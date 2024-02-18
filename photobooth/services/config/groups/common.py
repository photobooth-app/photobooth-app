"""
AppConfig class providing central config

"""

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class EnumDebugLevel(str, Enum):
    """enum for debuglevel"""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"


class GroupCommon(BaseModel):
    """Common config for photobooth."""

    model_config = ConfigDict(title="Common Config")

    countdown_capture_first: float = Field(
        default=2.0,
        ge=0,
        le=20,
        description="Countdown in seconds, started when user start a capture process",
    )

    countdown_capture_second_following: float = Field(
        default=1.0,
        ge=0,
        le=20,
        description="Countdown in seconds, used for second and following captures for collages",
    )
    countdown_camera_capture_offset: float = Field(
        default=0.25,
        ge=0,
        le=20,
        description="Trigger camera capture by offset earlier (in seconds). 0 trigger exactly when countdown is 0. Use to compensate for delay in camera processing for better UX.",
    )
    collage_automatic_capture_continue: bool = Field(
        default=True,
        description="Automatically continue with second and following images to capture for collage. No user interaction in between.",
    )
    collage_approve_autoconfirm_timeout: float = Field(
        default=15.0,
        description="If user is required to approve collage captures, after this timeout, the job continues and user confirmation is assumed.",
    )

    gallery_show_individual_images: bool = Field(
        default=False,
        description="Show individual images of collages/animations in the gallery. Hidden images are still stored in the data folder. (Note: changing this setting will not change visibility of already captured images).",
    )

    DEBUG_LEVEL: EnumDebugLevel = Field(
        title="Debug Level",
        default=EnumDebugLevel.DEBUG,
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
