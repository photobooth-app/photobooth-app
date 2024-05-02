"""
AppConfig class providing central config

"""

from pydantic import BaseModel, ConfigDict, Field


class GroupMisc(BaseModel):
    """
    Quite advanced or experimental, usually not necessary to touch. Can change any time.
    """

    model_config = ConfigDict(title="Miscellaneous Config")

    video_bitrate: int = Field(
        default=3000,
        ge=1000,
        le=10000,
        description="Video quality bitrate in k.",
    )

    video_compatibility_mode: bool = Field(
        default=False,
        description="Enable for improved video compatibility on iOS devices. Might reduce resulting quality slightly.",
    )
