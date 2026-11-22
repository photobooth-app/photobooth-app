from typing import Literal

from pydantic import BaseModel, Field, FilePath


class Watermark(BaseModel):
    enable: bool = Field(
        default=False,
        description="Enable watermark to be applied to the final processed image.",
    )
    image: FilePath | None = Field(
        default=None,
        description="Image to overlay on the final result. Use a PNG with transparency; files need to be located in working directory/userdata/*.",
        json_schema_extra={"list_api": "/api/admin/enumerate/userfiles"},
    )
    fill_method: Literal["cover", "contain"] = Field(
        default="cover",
        description="Scale and center the watermark while preserving its aspect ratio. Cover fills the image and may crop the watermark; contain shows the entire watermark.",
    )
