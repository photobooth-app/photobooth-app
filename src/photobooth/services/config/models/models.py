from pathlib import Path
from typing import Annotated

from pydantic import BaseModel, BeforeValidator, Field, FilePath, NonNegativeInt, PositiveInt
from pydantic_extra_types.color import Color

from ...mediaprocessing.steps.image import PluginFilters
from ..validators import ensure_demoassets


class TextsConfig(BaseModel):
    text: str = ""
    pos_x: NonNegativeInt = 50
    pos_y: NonNegativeInt = 50
    rotate: int = 0
    font_size: PositiveInt = 40
    font: Annotated[FilePath | None, BeforeValidator(ensure_demoassets)] = Field(
        default=Path("userdata/demoassets/fonts/Roboto-Bold.ttf"),
        json_schema_extra={"list_api": "/api/admin/enumerate/userfiles"},
    )
    color: Color = Color("#cd1c18")


class CollageMergeDefinition(BaseModel):
    description: str = Field(
        default="",
        description="A description just for you.",
    )
    pos_x: NonNegativeInt = Field(
        default=50,
        description="Position of the image's left edge in reference to the left edge of the canvas.",
    )
    pos_y: NonNegativeInt = Field(
        default=50,
        description="Position of the image's top edge in reference to the top edge of the canvas.",
    )
    pos_z: NonNegativeInt = Field(
        default=0,
        description="Layer the image is mounted to. Higher numbered layers are stacked in front of lower layers. If a number is used multiple times, the sequence of capture is used.",
    )
    width: NonNegativeInt = Field(
        default=600,
        description="Width the image is fit to on the canvas. If the aspect ratio mismatches, the algorithm chooses to cover the width/height avoiding blank areas in favor to cut off some parts of the image.",
    )
    height: NonNegativeInt = Field(
        default=600,
        description="Height the image is fit to on the canvas. If the aspect ratio mismatches, the algorithm chooses to cover the width/height avoiding blank areas in favor to cut off some parts of the image.",
    )
    rotate: int = Field(
        default=0,
        description="Rotate the image before merging. Positive numbers rotate counterclockwise, negative clockwise.",
    )
    predefined_image: Annotated[FilePath | None, BeforeValidator(ensure_demoassets)] = Field(
        default=None,
        description="Use a predefined image instead of a capture from camera for static content.",
        json_schema_extra={"list_api": "/api/admin/enumerate/userfiles"},
    )
    image_filter: PluginFilters = Field(
        default=PluginFilters("original"),
    )


class AnimationMergeDefinition(BaseModel):
    duration: NonNegativeInt = 2000
    predefined_image: Annotated[FilePath | None, BeforeValidator(ensure_demoassets)] = Field(
        default=None,
        json_schema_extra={"list_api": "/api/admin/enumerate/userfiles"},
    )
    image_filter: PluginFilters = Field(
        default=PluginFilters("original"),
    )
