"""
AppConfig class providing central config

"""

from pydantic import BaseModel, ConfigDict, Field


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
        description="Dimension of longer side used for scaling full images. Shorter side of the image is calculated to keep aspect ratio. For performance choose as low as possible but still gives decent print quality. Example: 1500/6inch=250dpi",
    )
    preview_still_length: int = Field(
        default=1200,
        ge=200,
        le=2500,
        description="Dimension of longer side used for scaling previews. Shorter side of the image is calculated to keep aspect ratio.",
    )
    thumbnail_still_length: int = Field(
        default=400,
        ge=100,
        le=1000,
        description="Dimension of longer side used for scaling thumbnails. Shorter side of the image is calculated to keep aspect ratio.",
    )

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

    removechromakey_enable: bool = Field(
        default=False,
        description="Apply chromakey greenscreen removal from captured images",
    )
    removechromakey_keycolor: int = Field(
        default=110,
        ge=0,
        le=360,
        description="Color (H) in HSV colorspace to remove on 360° scale.",
    )
    removechromakey_tolerance: int = Field(
        default=10,
        ge=1,
        le=50,
        description="Tolerance for color (H) on chromakey color removal.",
    )
