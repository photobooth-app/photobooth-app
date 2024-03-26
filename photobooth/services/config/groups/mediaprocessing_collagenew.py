"""
AppConfig class providing central config

"""

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, NonNegativeInt, PositiveInt
from pydantic_extra_types.color import Color


class EnumPilgramFilter(str, Enum):
    """enum to choose image filter from, pilgram filter"""

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
    font: str = "fonts/Roboto-Bold.ttf"
    color: Color = Color("red").as_hex()


class CollageMergeDefinition(BaseModel):
    pos_x: NonNegativeInt = 50
    pos_y: NonNegativeInt = 50
    width: NonNegativeInt = 600
    height: NonNegativeInt = 600
    rotate: int = 0
    predefined_image: str = ""
    filter: EnumPilgramFilter = EnumPilgramFilter.original


class AnimationMergeDefinition(BaseModel):
    duration: NonNegativeInt = 2000
    predefined_image: str = ""
    filter: EnumPilgramFilter = EnumPilgramFilter.original


class GroupMediaprocessingPipelineCollage(BaseModel):
    """Configure stages how to process collage after capture."""

    model_config = ConfigDict(title="Process collage after capture")

    ## phase 1 per capture application on collage also. settings taken from PipelineImage if needed

    capture_fill_background_enable: bool = Field(
        default=False,
        description="Apply solid color background to captured image (useful only if image is extended or background removed)",
    )
    capture_fill_background_color: Color = Field(
        default=Color("blue").as_hex(),
        description="Solid color used to fill background.",
    )
    capture_img_background_enable: bool = Field(
        default=False,
        description="Add image from file to background (useful only if image is extended or background removed)",
    )
    capture_img_background_file: str = Field(
        default="backgrounds/pink-7761356_1920.jpg",
        description="Image file to use as background filling transparent area. File needs to be located in DATA_DIR/*",
    )

    ## phase 2 per collage settings.

    canvas_width: int = Field(
        default=1920,
        description="Width (X) in pixel of collage image. The higher the better the quality but also longer time to process. All processes keep aspect ratio.",
    )
    canvas_height: int = Field(
        default=1280,
        description="Height (Y) in pixel of collage image. The higher the better the quality but also longer time to process. All processes keep aspect ratio.",
    )
    canvas_merge_definition: list[CollageMergeDefinition] = Field(
        default=[
            CollageMergeDefinition(
                pos_x=160,
                pos_y=220,
                width=510,
                height=725,
                rotate=0,
                filter=EnumPilgramFilter.earlybird,
            ),
            CollageMergeDefinition(
                pos_x=705,
                pos_y=66,
                width=510,
                height=725,
                rotate=0,
                predefined_image="predefined_images/photobooth-collage-predefined-image.png",
                filter=EnumPilgramFilter.original,
            ),
            CollageMergeDefinition(
                pos_x=1245,
                pos_y=220,
                width=510,
                height=725,
                rotate=0,
                filter=EnumPilgramFilter.reyes,
            ),
        ],
        description="How to arrange single images in the collage. Pos_x/Pos_y measure in pixel starting 0/0 at top-left in image. Width/Height in pixels. Aspect ratio is kept always. Predefined image files are used instead a camera capture. File needs to be located in DATA_DIR/*",
    )
    canvas_fill_background_enable: bool = Field(
        default=False,
        description="Apply solid color background to collage",
    )
    canvas_fill_background_color: Color = Field(
        default=Color("green").as_hex(),
        description="Solid color used to fill background.",
    )
    canvas_img_background_enable: bool = Field(
        default=False,
        description="Add image from file to background.",
    )
    canvas_img_background_file: str = Field(
        default="backgrounds/pink-7761356_1920.jpg",
        description="Image file to use as background filling transparent area. File needs to be located in userdata/*",
    )
    canvas_img_front_enable: bool = Field(
        default=True,
        description="Overlay image on canvas image.",
    )
    canvas_img_front_file: str = Field(
        default="frames/pixabay-poster-2871536_1920.png",
        description="Image file to paste on top over photos and backgrounds. Photos are visible only through transparant parts. Image needs to be transparent (PNG). File needs to be located in DATA_DIR/*",
    )
    canvas_texts_enable: bool = Field(
        default=True,
        description="General enable apply texts below.",
    )
    canvas_texts: list[TextsConfig] = Field(
        default=[
            TextsConfig(
                text="Have a nice day :)",
                pos_x=200,
                pos_y=1100,
                rotate=1,
                color=Color("#333").as_hex(),
            ),
        ],
        description="Text to overlay on final collage. Pos_x/Pos_y measure in pixel starting 0/0 at top-left in image. Font to use in text stages. File needs to be located in DATA_DIR/*",
    )


class GroupCollageProcess(BaseModel):
    """Configure stages how to process collage after capture."""

    model_config = ConfigDict(title="New Test!")

    other_general_settings: int = Field(
        default=900,
        description="Height (Y) in pixel of animation image (GIF). The higher the better the quality but also longer time to process. All processes keep aspect ratio.",
    )

    collage_pipeline_sets: list[GroupMediaprocessingPipelineCollage] = Field(
        default=[GroupMediaprocessingPipelineCollage()],
        description="yes, this is another level, maybe expandable?",
    )
