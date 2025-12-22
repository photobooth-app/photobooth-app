"""
AppConfig class providing central config

"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

RembgModelType = Literal["modnet", "u2netp", "u2net"]


class GroupMediaprocessing(BaseModel):
    """Configure stages how to process images after capture."""

    model_config = ConfigDict(title="Process media after capture")

    full_still_length: int = Field(
        json_schema_extra={"computeIntense": True},
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
        json_schema_extra={"ui_schema_extra": {"slider": True}},
    )

    video_compatibility_mode: bool = Field(
        default=True,
        description="Enable for improved video compatibility on iOS devices and Firefox. Might reduce resulting quality slightly.",
    )

    remove_background_model: RembgModelType = Field(
        default="modnet",
        json_schema_extra={"computeIntense": True},
        description="Select from predefined models. Modnet and u2netp are packaged with the app, other models will be downloaded on demand and cached, so on first use of other models, the app needs internet access. u2netp is a reduced model that is fastest, modnet usually only slightly slower but provides good results.",
    )

    fileformat_animations: Literal["webp", "avif", "gif"] = Field(
        default="webp",
        description="Format in which animations are stored. WebP is recommended nowadays. AVIF is a newer format, encodes fast, produces smallest files but is not yet broadly compatible. GIF is lower quality (max 256 colors), more compute intensive to encode but offers best compatibility. GIF is deprecated here.",
    )

    fileformat_multicamera: Literal["mp4", "webp", "avif", "gif"] = Field(
        default="mp4",
        description="Format in which wigglegrams are stored. MP4 is recommended for quality and filesize as well as compatibility. WebP/AVIF are recommended over MP4 and GIF but still lack support sharing via WhatsApp. GIF is lower quality (max 256 colors), more compute intensive to encode but offers best compatibility. GIF is deprecated here.",
    )
