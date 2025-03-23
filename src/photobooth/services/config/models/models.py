from pathlib import Path
from typing import Annotated

from pydantic import BaseModel, BeforeValidator, Field, FilePath, NonNegativeInt, PositiveInt
from pydantic_extra_types.color import Color

from photobooth.services.mediaprocessing.steps.image import PluginFilters

from ..validators import ensure_demoassets


class TextsConfig(BaseModel):
    text: str = ""
    pos_x: NonNegativeInt = 50
    pos_y: NonNegativeInt = 50
    rotate: int = 0
    font_size: PositiveInt = 40
    font: Annotated[FilePath | None, BeforeValidator(ensure_demoassets)] = Field(
        default=Path("userdata/demoassets/fonts/Roboto-Bold.ttf"),
        json_schema_extra={"files_list_api": "/api/admin/files/search"},
    )
    color: Color = Color("red")


class CollageMergeDefinition(BaseModel):
    description: str = ""
    pos_x: NonNegativeInt = 50
    pos_y: NonNegativeInt = 50
    width: NonNegativeInt = 600
    height: NonNegativeInt = 600
    rotate: int = 0
    predefined_image: Annotated[FilePath | None, BeforeValidator(ensure_demoassets)] = Field(
        default=None,
        json_schema_extra={"files_list_api": "/api/admin/files/search"},
    )
    image_filter: PluginFilters = PluginFilters("original")


class AnimationMergeDefinition(BaseModel):
    duration: NonNegativeInt = 2000
    predefined_image: Annotated[FilePath | None, BeforeValidator(ensure_demoassets)] = Field(
        default=None,
        json_schema_extra={"files_list_api": "/api/admin/files/search"},
    )
    image_filter: PluginFilters = PluginFilters("original")
