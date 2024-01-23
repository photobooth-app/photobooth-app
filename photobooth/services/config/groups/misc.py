"""
AppConfig class providing central config

"""


from pydantic import BaseModel, ConfigDict, Field


class GroupMisc(BaseModel):
    """
    Quite advanced or experimental, usually not necessary to touch. Can change any time.
    """

    model_config = ConfigDict(title="Miscellaneous Config")

    video_duration: int = Field(
        default=10,
        ge=1,
        le=30,
        description="Duration of a video in seconds. The user can stop recording earlier but cannot take longer videos.",
    )

    video_quality: int = Field(
        default=8,
        ge=1,
        le=10,
        description="Video quality.",
    )
