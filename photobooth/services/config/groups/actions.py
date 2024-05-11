from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
from pydantic_extra_types.color import Color

from ..models.models import AnimationMergeDefinition, CollageMergeDefinition, PilgramFilter, TextsConfig


class GroupFrontpageTriggerActions(BaseModel):
    """
    Frontpage triggers configuration.
    """

    model_config = ConfigDict(title="Frontpage triggers configuration")

    # ui config
    # use_advanced_ui_buttons: bool = Field(
    #     default=False,
    #     description="Use below defined buttons instead automatic button rendering.",
    # )

    title: str = ""
    icon: str = ""
    klass: str = ""


class GroupKeyboardTriggerActions(BaseModel):
    """
    Configure trigger the user can interact with. Sources are GPIO and keyboard.
    """

    model_config = ConfigDict(title="Keyboard triggers configuration")

    # keyboard config
    # keyboard_input_enabled: bool = Field(
    #     default=False,
    #     description="Enable keyboard input globally. Keyup is catched in browsers connected to the app.",
    # )
    keycode: str = Field(
        default="",
        description="Define keyboard keys to trigger actions.",
    )


class GroupGpioTriggerActions(BaseModel):
    """
    Configure trigger the user can interact with. Sources are GPIO and keyboard.
    """

    model_config = ConfigDict(title="GPIO triggers configuration")

    # gpio config
    # gpio_enabled: bool = Field(
    #     default=False,
    #     description="Enable GPIO globally. Works only on Raspberry Pi.",
    # )

    pin: int = None

    trigger_on: Literal["pressed", "released", "longpress"] = Field(
        default="pressed",
        description="Trigger action when button pressed (contact closed), released (contact open after closed) or longpress (hold for 0.6 seconds).",
    )


class GroupTrigger(BaseModel):
    """
    Configure trigger the user can interact with. Sources are GPIO and keyboard.
    """

    model_config = ConfigDict(title="Trigger action configuration")

    # ui config
    frontpage_trigger_actions: GroupFrontpageTriggerActions = GroupFrontpageTriggerActions()
    keyboard_trigger_actions: GroupKeyboardTriggerActions = GroupKeyboardTriggerActions()
    gpio_trigger_actions: GroupGpioTriggerActions = GroupGpioTriggerActions()


class GroupSingleImageProcessing(BaseModel):
    """Configure stages how to process images after capture."""

    model_config = ConfigDict(title="Postprocess single captures")

    filter: PilgramFilter = Field(
        title="Pic1 Filter",
        default=PilgramFilter.original,
        description="Instagram-like filter to apply per default. 'original' applies no filter.",
    )
    fill_background_enable: bool = Field(
        default=False,
        description="Apply solid color background to captured image (useful only if image is extended or background removed)",
    )
    fill_background_color: Color = Field(
        default=Color("blue").as_hex(),
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
        default="frames/pixabay-holidays-1798208_1920.png",
        description="Image file to which the captured image is mounted to. Frame determines the output image size! Photos are visible through transparant parts. Image needs to be transparent (PNG). File needs to be located in userdata/*",
    )
    texts_enable: bool = Field(
        default=True,
        description="General enable apply texts below.",
    )
    texts: list[TextsConfig] = Field(
        default=[
            TextsConfig(
                text="Made with the photobooth-app",  # use {date} and {time} to add dynamic texts; cannot use in default because tests will fail that compare images
                pos_x=100,
                pos_y=1300,
                rotate=0,
                color=Color("#ccc").as_hex(),
            ),
        ],
        description="Text to overlay on images after capture. Pos_x/Pos_y measure in pixel starting 0/0 at top-left in image. Font to use in text stages. File needs to be located in DATA_DIR/*",
    )


class GroupCollageProcessing(BaseModel):
    """Configure stages how to process collage after capture."""

    model_config = ConfigDict(title="Process collage after capture")

    ask_approval_each_capture: bool = Field(
        default=True,
        description="Stop after every capture to ask user if he would like to continue or redo the capture. If disabled captures are granted as approved always.",
    )
    approve_autoconfirm_timeout: float = Field(
        default=15.0,
        description="If user is required to approve collage captures, after this timeout, the job continues and user confirmation is assumed.",
    )

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
    merge_definition: list[CollageMergeDefinition] = Field(
        default=[
            CollageMergeDefinition(
                pos_x=160,
                pos_y=220,
                width=510,
                height=725,
                rotate=0,
                filter=PilgramFilter.earlybird,
            ),
            CollageMergeDefinition(
                pos_x=705,
                pos_y=66,
                width=510,
                height=725,
                rotate=0,
                predefined_image="predefined_images/photobooth-collage-predefined-image.png",
                filter=PilgramFilter.original,
            ),
            CollageMergeDefinition(
                pos_x=1245,
                pos_y=220,
                width=510,
                height=725,
                rotate=0,
                filter=PilgramFilter.reyes,
            ),
        ],
        description="How to arrange single images in the collage. Pos_x/Pos_y measure in pixel starting 0/0 at top-left in image. Width/Height in pixels. Aspect ratio is kept always. Predefined image files are used instead a camera capture. File needs to be located in DATA_DIR/*",
    )

    gallery_hide_individual_images: bool = Field(
        default=False,
        description="Hide individual images of collages in the gallery. Hidden images are still stored in the data folder. (Note: changing this setting will not change visibility of already captured images).",
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


class GroupAnimationProcessing(BaseModel):
    """Configure stages how to process collage after capture."""

    model_config = ConfigDict(title="Process Animation (GIF) after capture")

    ask_approval_each_capture: bool = Field(
        default=False,
        description="Stop after every capture to ask user if he would like to continue or redo the capture. If disabled captures are granted as approved always.",
    )
    approve_autoconfirm_timeout: float = Field(
        default=15.0,
        description="If user is required to approve animation captures, after this timeout, the job continues and user confirmation is assumed.",
    )

    ## phase 2 per collage settings.

    canvas_width: int = Field(
        default=1500,
        description="Width (X) in pixel of animation image (GIF). The higher the better the quality but also longer time to process. All processes keep aspect ratio.",
    )
    canvas_height: int = Field(
        default=900,
        description="Height (Y) in pixel of animation image (GIF). The higher the better the quality but also longer time to process. All processes keep aspect ratio.",
    )
    merge_definition: list[AnimationMergeDefinition] = Field(
        default=[
            AnimationMergeDefinition(filter=PilgramFilter.crema),
            AnimationMergeDefinition(filter=PilgramFilter.inkwell),
            AnimationMergeDefinition(
                duration=4000,
                filter=PilgramFilter.original,
                predefined_image="predefined_images/photobooth-gif-animation-predefined-image.png",
            ),
        ],
        description="Sequence images in an animated GIF. Predefined image files are used instead a camera capture. File needs to be located in DATA_DIR/*",
    )

    gallery_hide_individual_images: bool = Field(
        default=False,
        description="Hide individual images of animations in the gallery. Hidden images are still stored in the data folder. (Note: changing this setting will not change visibility of already captured images).",
    )


class GroupVideoProcessing(BaseModel):
    """Configure stages how to process collage after capture."""

    model_config = ConfigDict(title="Video Actions")

    video_duration: int = Field(
        default=5,
        description="Maximum duration of the video. Users can stop earlier or capture is automatically stopped after set time.",
    )
    boomerang: bool = Field(
        default=False,
        description="Create boomerang videos, the video is replayed reverse automatically.",
    )
    video_framerate: int = Field(
        default=25,
        ge=1,
        le=30,
        description="Video framerate (frames per second).",
    )


class GroupPrintingProcessing(BaseModel):
    """Configure options to print images."""

    model_config = ConfigDict(title="Printing Actions")

    printing_command: str = Field(
        default="mspaint /p {filename}",
        description="Command issued to print. Use {filename} as placeholder for the JPEG image to be printed.",
    )
    printing_blocked_time: int = Field(
        default=10,
        description="Block queue print until time is passed. Time in seconds.",
    )


class GroupSingleImageConfigurationSet(BaseModel):
    """Configure stages how to process images after capture."""

    model_config = ConfigDict(title="Postprocess single captures")
    name: str = Field(
        default="default single image settings",
        description="Name to identify, only used for display in admin center.",
    )
    actions: GroupSingleImageProcessing = GroupSingleImageProcessing()
    trigger: GroupTrigger = GroupTrigger(
        gpio_trigger_actions=GroupGpioTriggerActions(pin=27),
        keyboard_trigger_actions=GroupKeyboardTriggerActions(keycode="i"),
    )


class GroupCollageConfigurationSet(BaseModel):
    """Configure stages how to process images after capture."""

    model_config = ConfigDict(title="Postprocess single captures")
    name: str = Field(
        default="default collage settings",
        description="Name to identify, only used for display in admin center.",
    )
    actions: GroupCollageProcessing = GroupCollageProcessing()
    trigger: GroupTrigger = GroupTrigger(
        gpio_trigger_actions=GroupGpioTriggerActions(pin=22),
        keyboard_trigger_actions=GroupKeyboardTriggerActions(keycode="c"),
    )


class GroupAnimationConfigurationSet(BaseModel):
    """Configure stages how to process images after capture."""

    model_config = ConfigDict(title="Postprocess single captures")
    name: str = Field(
        default="default animation settings",
        description="Name to identify, only used for display in admin center.",
    )
    actions: GroupAnimationProcessing = GroupAnimationProcessing()
    trigger: GroupTrigger = GroupTrigger(
        gpio_trigger_actions=GroupGpioTriggerActions(pin=24),
        keyboard_trigger_actions=GroupKeyboardTriggerActions(keycode="g"),
    )


class GroupVideoConfigurationSet(BaseModel):
    """Configure stages how to process images after capture."""

    model_config = ConfigDict(title="Postprocess single captures")
    name: str = Field(
        default="default video settings",
        description="Name to identify, only used for display in admin center.",
    )
    actions: GroupVideoProcessing = GroupVideoProcessing()
    trigger: GroupTrigger = GroupTrigger(
        gpio_trigger_actions=GroupGpioTriggerActions(pin=26),
        keyboard_trigger_actions=GroupKeyboardTriggerActions(keycode="v"),
    )


class GroupPrintingConfigurationSet(BaseModel):
    """Configure stages how to process mediaitem before printing on paper."""

    model_config = ConfigDict(title="Process mediaitem before printing on paper")

    name: str = Field(
        default="default print settings",
        description="Name to identify, only used for display in admin center.",
    )
    actions: GroupPrintingProcessing = GroupPrintingProcessing()
    trigger: GroupTrigger = GroupTrigger(
        gpio_trigger_actions=GroupGpioTriggerActions(pin=23),
        keyboard_trigger_actions=GroupKeyboardTriggerActions(keycode="p"),
    )


class GroupActions(BaseModel):
    """
    Configure actions like capture photo, video, collage and animations.
    """

    model_config = ConfigDict(title="Actions configuration")

    image: list[GroupSingleImageConfigurationSet] = Field(
        default=[
            GroupSingleImageConfigurationSet(),
        ],
        description="Capture single images.",
    )

    collage: list[GroupCollageConfigurationSet] = Field(
        default=[
            GroupCollageConfigurationSet(),
        ],
        description="Capture collages consist of one or more still images.",
    )

    animation: list[GroupAnimationConfigurationSet] = Field(
        default=[
            GroupAnimationConfigurationSet(),
        ],
        description="Capture GIF animation sequence consist of one or more still images. It's not a video but a low number of still images.",
    )

    video: list[GroupVideoConfigurationSet] = Field(
        default=[
            GroupVideoConfigurationSet(),
        ],
        description="Capture videos from live streaming backend.",
    )


class GroupPrintActions(BaseModel):
    """
    Configure actions like capture photo, video, collage and animations.
    """

    model_config = ConfigDict(title="Actions configuration")

    print: list[GroupPrintingConfigurationSet] = Field(
        default=[
            GroupPrintingConfigurationSet(),
        ],
        description="Process media items before printing.",
    )
