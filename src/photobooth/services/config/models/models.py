from pathlib import Path

from pydantic import BaseModel, Field, FilePath, NonNegativeInt, PositiveInt
from pydantic_extra_types.color import Color

from photobooth.services.mediaprocessing.steps.image import PluginFilters


class TextsConfig(BaseModel):
    text: str = ""
    pos_x: NonNegativeInt = 50
    pos_y: NonNegativeInt = 50
    rotate: int = 0
    font_size: PositiveInt = 40
    font: FilePath | None = Field(
        default=Path("userdata/demoassets/fonts/Roboto-Bold.ttf"), json_schema_extra={"files_list_api": "/api/admin/files/search"}
    )
    color: Color = Color("red")


class SinglePictureDefinition(BaseModel):
    image_filter: PluginFilters = PluginFilters("original")
    fill_background_enable: bool = False
    fill_background_color: Color = Color("blue")
    img_background_enable: bool = False
    img_background_file: FilePath | None = Field(default=None, json_schema_extra={"files_list_api": "/api/admin/files/search"})
    img_frame_enable: bool = False
    img_frame_file: FilePath | None = Field(default=None, json_schema_extra={"files_list_api": "/api/admin/files/search"})
    texts_enable: bool = False
    texts: list[TextsConfig] = []


class CollageMergeDefinition(BaseModel):
    description: str = ""
    pos_x: NonNegativeInt = 50
    pos_y: NonNegativeInt = 50
    width: NonNegativeInt = 600
    height: NonNegativeInt = 600
    rotate: int = 0
    predefined_image: FilePath | None = Field(default=None, json_schema_extra={"files_list_api": "/api/admin/files/search"})
    image_filter: PluginFilters = PluginFilters("original")


class AnimationMergeDefinition(BaseModel):
    duration: NonNegativeInt = 2000
    predefined_image: FilePath | None = Field(default=None, json_schema_extra={"files_list_api": "/api/admin/files/search"})
    image_filter: PluginFilters = PluginFilters("original")
