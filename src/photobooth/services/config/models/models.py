from pydantic import BaseModel, NonNegativeInt, PositiveInt
from pydantic_extra_types.color import Color

from photobooth.services.mediaprocessing.steps.image import PluginFilters


class TextsConfig(BaseModel):
    text: str = ""
    pos_x: NonNegativeInt = 50
    pos_y: NonNegativeInt = 50
    rotate: int = 0
    font_size: PositiveInt = 40
    font: str = "userdata/fonts/Roboto-Bold.ttf"
    color: Color = Color("red")


class SinglePictureDefinition(BaseModel):
    filter: PluginFilters = PluginFilters.original
    fill_background_enable: bool = False
    fill_background_color: Color = Color("blue")
    img_background_enable: bool = False
    img_background_file: str = "userdata/backgrounds/pink-7761356_1920.jpg"
    img_frame_enable: bool = False
    img_frame_file: str = "userdata/frames/frame_image_photobooth-app.png"
    texts_enable: bool = False
    texts: list[TextsConfig] = []


class CollageMergeDefinition(BaseModel):
    description: str = ""
    pos_x: NonNegativeInt = 50
    pos_y: NonNegativeInt = 50
    width: NonNegativeInt = 600
    height: NonNegativeInt = 600
    rotate: int = 0
    predefined_image: str = ""
    filter: PluginFilters = PluginFilters.original


class AnimationMergeDefinition(BaseModel):
    duration: NonNegativeInt = 2000
    predefined_image: str = ""
    filter: PluginFilters = PluginFilters.original
