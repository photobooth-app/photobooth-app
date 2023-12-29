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
    color: Color = Color("red").as_named()


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


class GroupMediaprocessingPipelineSingleImage(BaseModel):
    """Configure stages how to process images after capture."""

    model_config = ConfigDict(title="Postprocess single captures")

    pipeline_enable: bool = Field(
        default=True,
        description="Enable/Disable processing pipeline completely",
    )

    filter: EnumPilgramFilter = Field(
        title="Pic1 Filter",
        default=EnumPilgramFilter.original,
        description="Instagram-like filter to apply per default. 'original' applies no filter.",
    )
    fill_background_enable: bool = Field(
        default=False,
        description="Apply solid color background to captured image (useful only if image is extended or background removed)",
    )
    fill_background_color: Color = Field(
        default=Color("blue").as_named(),
        description="Solid color used to fill background.",
    )
    img_background_enable: bool = Field(
        default=False,
        description="Add image from file to background (useful only if image is extended or background removed)",
    )
    img_background_file: str = Field(
        default="backgrounds/pink-7761356_1920.jpg",
        description="Image file to use as background filling transparent area. File needs to be located in DATA_DIR/*",
    )
    img_frame_enable: bool = Field(
        default=True,
        description="Mount captured image to frame.",
    )
    img_frame_file: str = Field(
        default="frames/polaroid-6125402_1pic.png",
        description="Image file to which the captured image is mounted to. Frame determines the output image size! Photos are visible through transparant parts. Image needs to be transparent (PNG). File needs to be located in userdata/*",
    )
    texts_enable: bool = Field(
        default=True,
        description="General enable apply texts below.",
    )
    texts: list[TextsConfig] = Field(
        default=[
            TextsConfig(
                text="Some Text!",  # use {date} and {time} to add dynamic texts; cannot use in default because tests will fail that compare images
                pos_x=300,
                pos_y=900,
                rotate=-3,
                color=Color("black"),
            ),
        ],
        description="Text to overlay on images after capture. Pos_x/Pos_y measure in pixel starting 0/0 at top-left in image. Font to use in text stages. File needs to be located in DATA_DIR/*",
    )


class GroupMediaprocessingPipelineCollage(BaseModel):
    """Configure stages how to process collage after capture."""

    model_config = ConfigDict(title="Process collage after capture")

    ## phase 1 per capture application on collage also. settings taken from PipelineImage if needed

    capture_fill_background_enable: bool = Field(
        default=False,
        description="Apply solid color background to captured image (useful only if image is extended or background removed)",
    )
    capture_fill_background_color: Color = Field(
        default=Color("blue").as_named(),
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
        default=1080,
        description="Height (Y) in pixel of collage image. The higher the better the quality but also longer time to process. All processes keep aspect ratio.",
    )
    canvas_merge_definition: list[CollageMergeDefinition] = Field(
        default=[
            CollageMergeDefinition(pos_x=215, pos_y=122, width=660, height=660, rotate=-2, filter=EnumPilgramFilter.earlybird),
            CollageMergeDefinition(
                pos_x=1072,
                pos_y=122,
                width=660,
                height=660,
                rotate=-3,
                filter=EnumPilgramFilter.mayfair,
                predefined_image="predefined_images/pexels-marcelo-miranda-7708722.jpg",
            ),
        ],
        description="How to arrange single images in the collage. Pos_x/Pos_y measure in pixel starting 0/0 at top-left in image. Width/Height in pixels. Aspect ratio is kept always. Predefined image files are used instead a camera capture. File needs to be located in DATA_DIR/*",
    )
    canvas_fill_background_enable: bool = Field(
        default=False,
        description="Apply solid color background to collage",
    )
    canvas_fill_background_color: Color = Field(
        default=Color("green").as_named(),
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
        default="frames/polaroid-6125402_1920.png",
        description="Image file to paste on top over photos and backgrounds. Photos are visible only through transparant parts. Image needs to be transparent (PNG). File needs to be located in DATA_DIR/*",
    )
    canvas_texts_enable: bool = Field(
        default=True,
        description="General enable apply texts below.",
    )
    canvas_texts: list[TextsConfig] = Field(
        default=[
            TextsConfig(
                text="Nice Collage Text!",
                pos_x=300,
                pos_y=800,
                rotate=-3,
                color=Color("black"),
            ),
        ],
        description="Text to overlay on final collage. Pos_x/Pos_y measure in pixel starting 0/0 at top-left in image. Font to use in text stages. File needs to be located in DATA_DIR/*",
    )


class GroupMediaprocessingPipelineAnimation(BaseModel):
    """Configure stages how to process collage after capture."""

    model_config = ConfigDict(title="Process Animation (GIF) after capture")

    ## phase 2 per collage settings.

    canvas_width: int = Field(
        default=1500,
        description="Width (X) in pixel of animation image (GIF). The higher the better the quality but also longer time to process. All processes keep aspect ratio.",
    )
    canvas_height: int = Field(
        default=900,
        description="Height (Y) in pixel of animation image (GIF). The higher the better the quality but also longer time to process. All processes keep aspect ratio.",
    )
    sequence_merge_definition: list[AnimationMergeDefinition] = Field(
        default=[
            AnimationMergeDefinition(filter=EnumPilgramFilter.crema),
            AnimationMergeDefinition(
                duration=4000,
                filter=EnumPilgramFilter.helena,
                predefined_image="predefined_images/pexels-marcelo-miranda-7708722.jpg",
            ),
        ],
        description="Sequence images in an animated GIF. Predefined image files are used instead a camera capture. File needs to be located in DATA_DIR/*",
    )


class GroupMediaprocessingPipelinePrint(BaseModel):
    """Configure stages how to process mediaitem before printing on paper."""

    model_config = ConfigDict(title="Process mediaitem before printing on paper")
