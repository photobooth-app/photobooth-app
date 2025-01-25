from enum import Enum

from pydantic import BaseModel, NonNegativeInt, PositiveInt
from pydantic_extra_types.color import Color


class KeyboardTriggerMapAction(BaseModel):
    keycode: str = ""
    action: str = ""


class GpioTriggerMapAction(BaseModel):
    pin: int = None
    on: str = "pressed,hold,released"
    action: str = ""


class PilgramFilter(str, Enum):
    """Choose a Pilgram2 filter manipulating the images colors. Original means no filter to apply."""

    # List[LiteralType] seems not yet supported by Pydantic. So we stick with enums for now despite they render not so nice in jsonforms

    original = "original"

    _1977 = "_1977"
    aden = "aden"
    ashby = "ashby"
    amaro = "amaro"
    brannan = "brannan"
    brooklyn = "brooklyn"
    charmes = "charmes"
    clarendon = "clarendon"
    crema = "crema"
    dogpatch = "dogpatch"
    earlybird = "earlybird"
    gingham = "gingham"
    ginza = "ginza"
    hefe = "hefe"
    helena = "helena"
    hudson = "hudson"
    inkwell = "inkwell"
    juno = "juno"
    kelvin = "kelvin"
    lark = "lark"
    lofi = "lofi"
    ludwig = "ludwig"
    maven = "maven"
    mayfair = "mayfair"
    moon = "moon"
    nashville = "nashville"
    perpetua = "perpetua"
    poprocket = "poprocket"
    reyes = "reyes"
    rise = "rise"
    sierra = "sierra"
    skyline = "skyline"
    slumber = "slumber"
    stinson = "stinson"
    sutro = "sutro"
    toaster = "toaster"
    valencia = "valencia"
    walden = "walden"
    willow = "willow"
    xpro2 = "xpro2"


class TextsConfig(BaseModel):
    text: str = ""
    pos_x: NonNegativeInt = 50
    pos_y: NonNegativeInt = 50
    rotate: int = 0
    font_size: PositiveInt = 40
    font: str = "userdata/fonts/Roboto-Bold.ttf"
    color: Color = Color("red").as_hex()


class SinglePictureDefinition(BaseModel):
    filter: PilgramFilter = PilgramFilter.original
    fill_background_enable: bool = False
    fill_background_color: Color = Color("blue").as_hex()
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
    filter: PilgramFilter = PilgramFilter.original


class AnimationMergeDefinition(BaseModel):
    duration: NonNegativeInt = 2000
    predefined_image: str = ""
    filter: PilgramFilter = PilgramFilter.original
