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
    LIVEPREVIEW_QUALITY: int = Field(
        default=80,
        ge=10,
        le=100,
        description="Livepreview stream JPEG image quality on supported backends",
        json_schema_extra={"ui_component": "QSlider"},
    )
    THUMBNAIL_STILL_QUALITY: int = Field(
        default=60,
        ge=10,
        le=100,
        description="Still JPEG thumbnail quality, thumbs used in gallery list",
        json_schema_extra={"ui_component": "QSlider"},
    )
    PREVIEW_STILL_QUALITY: int = Field(
        default=75,
        ge=10,
        le=100,
        description="Still JPEG preview quality, preview still shown in gallery detail",
        json_schema_extra={"ui_component": "QSlider"},
    )

    FULL_STILL_WIDTH: int = Field(
        default=1500,
        ge=800,
        le=5000,
        description="Width of resized full image with filters applied. For performance choose as low as possible but still gives decent print quality. Example: 1500/6inch=250dpi",
    )
    PREVIEW_STILL_WIDTH: int = Field(
        default=1200,
        ge=200,
        le=2500,
        description="Width of resized preview image, height is automatically calculated to keep aspect ratio",
    )
    THUMBNAIL_STILL_WIDTH: int = Field(
        default=400,
        ge=100,
        le=1000,
        description="Width of resized thumbnail image, height is automatically calculated to keep aspect ratio",
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
