"""
AppConfig class providing central config

"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

RembgModelType = Literal["modnet", "u2netp", "u2net"]


class GroupMediaprocessing(BaseModel):
    """Configure stages how to process images after capture."""

    model_config = ConfigDict(title="Process media after capture")

    HIRES_STILL_QUALITY: int = Field(
        default=90,
        ge=10,
        le=100,
        description="Still JPEG full resolution quality, applied to download images and images with filter",
        json_schema_extra={"ui_component": "QSlider"},
    )

    full_still_length: int = Field(
        default=1500,
        ge=800,
        le=5000,
        description="Minimum dimension of the longer side used to scale full captures. The shorter side is calculated to keep aspect ratio. For best performance choose as low as possible but still gives decent print quality. Example: 1500/6inch=250dpi",
    )
    preview_still_length: int = Field(
        default=1200,
        ge=200,
        le=2500,
        description="Minimum dimension of the longer side used to scale preview captures. The shorter side is calculated to keep aspect ratio.",
    )
    thumbnail_still_length: int = Field(
        default=400,
        ge=100,
        le=1000,
        description="Minimum dimension of the longer side used to scale thumbnails captures. The shorter side is calculated to keep aspect ratio.",
    )

    video_bitrate: int = Field(
        default=3000,
        ge=1000,
        le=10000,
        description="Video quality bitrate in k.",
    )

    video_compatibility_mode: bool = Field(
        default=True,
        description="Enable for improved video compatibility on iOS devices and Firefox. Might reduce resulting quality slightly.",
    )

    removebackground_ai_enable: bool = Field(
        default=False,
        description="Remove the background using AI.",
    )
    removebackground_ai_model: RembgModelType = Field(
        default="modnet",
        description="Select from predefined models. Modnet and u2netp are packaged with the app, other models will be downloaded on demand and cached, so on first use of other models, the app needs internet access. u2netp is a reduced model that is fastest, modnet usually only slightly slower but provides good results.",
    )
