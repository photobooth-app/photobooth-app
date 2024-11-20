from pydantic import BaseModel, ConfigDict, Field, NonNegativeInt
from pydantic_extra_types.color import Color

from ..models.models import AnimationMergeDefinition, CollageMergeDefinition, PilgramFilter, TextsConfig
from ..models.trigger import GpioTrigger, KeyboardTrigger, Trigger, UiTrigger


class SingleImageJobControl(BaseModel):
    """Configure job control affecting the procedure."""

    model_config = ConfigDict(title="Job control for single captures")

    countdown_capture: float = Field(
        default=2.0,
        multiple_of=0.1,
        ge=0,
        le=20,
        description="Countdown in seconds, when user starts a capture process.",
    )


class MultiImageJobControl(BaseModel):
    """Configure job control affecting the procedure."""

    model_config = ConfigDict(title="Job control for multiple captures")

    countdown_capture: float = Field(
        default=2.0,
        multiple_of=0.1,
        ge=0,
        le=20,
        description="Countdown in seconds, when user starts a capture process",
    )
    countdown_capture_second_following: float = Field(
        default=1.0,
        multiple_of=0.1,
        ge=0,
        le=20,
        description="Countdown in seconds, used for second and following captures for collages",
    )

    ask_approval_each_capture: bool = Field(
        default=False,
        description="Stop after every capture to ask user if he would like to continue or redo the capture. If disabled captures are granted as approved always.",
    )
    approve_autoconfirm_timeout: float = Field(
        default=15.0,
        description="If user is required to approve collage captures, after this timeout, the job continues and user confirmation is assumed.",
    )

    gallery_hide_individual_images: bool = Field(
        default=False,
        description="Hide individual images of series in the gallery. Hidden images are still stored in the data folder. (Note: changing this setting will not change visibility of already captured images).",
    )


class VideoJobControl(BaseModel):
    """Configure job control affecting the procedure."""

    model_config = ConfigDict(title="Job control for video captures")

    countdown_capture: float = Field(
        default=2.0,
        multiple_of=0.1,
        ge=0,
        le=20,
        description="Countdown in seconds, when user starts a capture process.",
    )


class MulticameraJobControl(BaseModel):
    """Configure job control affecting the procedure."""

    model_config = ConfigDict(title="Job control for wigglegram-multicamera captures")

    countdown_capture: float = Field(
        default=2.0,
        multiple_of=0.1,
        ge=0,
        le=20,
        description="Countdown in seconds, when user starts a capture process.",
    )

    gallery_hide_individual_images: bool = Field(
        default=True,
        description="Hide individual images of multicam-capture in the gallery. Hidden images are still stored in the data folder. (Note: changing this setting will not change visibility of already captured images).",
    )


class SingleImageProcessing(BaseModel):
    """Configure stages how to process images after capture."""

    model_config = ConfigDict(title="Single captures processing after capture")

    filter: PilgramFilter = Field(default=PilgramFilter.original)

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
        default="",
        description="Image file to use as background filling transparent area. File needs to be located in DATA_DIR/*",
    )
    img_frame_enable: bool = Field(
        default=False,
        description="Mount captured image to frame.",
    )
    img_frame_file: str = Field(
        default="",
        description="Image file to which the captured image is mounted to. Frame determines the output image size! Photos are visible through transparant parts. Image needs to be transparent (PNG). File needs to be located in userdata/*",
    )
    texts_enable: bool = Field(
        default=False,
        description="General enable apply texts below.",
    )
    texts: list[TextsConfig] = Field(
        default=[],
        description="Text to overlay on images after capture. Pos_x/Pos_y measure in pixel starting 0/0 at top-left in image. Font to use in text stages. File needs to be located in DATA_DIR/*",
    )


class CollageProcessing(BaseModel):
    """Configure stages how to process collage after capture."""

    model_config = ConfigDict(title="Collage processing")

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
        default="",
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
        default="",
        description="Image file to use as background filling transparent area. File needs to be located in userdata/*",
    )
    canvas_img_front_enable: bool = Field(
        default=False,
        description="Overlay image on canvas image.",
    )
    canvas_img_front_file: str = Field(
        default="",
        description="Image file to paste on top over photos and backgrounds. Photos are visible only through transparant parts. Image needs to be transparent (PNG). File needs to be located in DATA_DIR/*",
    )
    canvas_texts_enable: bool = Field(
        default=False,
        description="General enable apply texts below.",
    )
    canvas_texts: list[TextsConfig] = Field(
        default=[],
        description="Text to overlay on final collage. Pos_x/Pos_y measure in pixel starting 0/0 at top-left in image. Font to use in text stages. File needs to be located in DATA_DIR/*",
    )


class AnimationProcessing(BaseModel):
    """Configure stages how to process collage after capture."""

    model_config = ConfigDict(title="Animation (GIF) processing after capture")

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
        default=[],
        description="Sequence images in an animated GIF. Predefined image files are used instead a camera capture. File needs to be located in DATA_DIR/*",
    )


class VideoProcessing(BaseModel):
    """Configure stages how to process collage after capture."""

    model_config = ConfigDict(title="Video Processing")

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


class MulticameraProcessing(BaseModel):
    """Configure stages how to process collage after capture."""

    model_config = ConfigDict(title="Wigglegram-multicamera processing")

    canvas_width: int = Field(
        default=1500,
        description="Width (X) in pixel of animation image (GIF). The higher the better the quality but also longer time to process. All processes keep aspect ratio.",
    )
    canvas_height: int = Field(
        default=900,
        description="Height (Y) in pixel of animation image (GIF). The higher the better the quality but also longer time to process. All processes keep aspect ratio.",
    )
    duration: NonNegativeInt = Field(
        default=125,
        description="Duration of each frame in milliseconds. Wigglegrams look good usually between 100-200ms duration.",
    )
    filter: PilgramFilter = Field(
        default=PilgramFilter.original,
    )


class SingleImageConfigurationSet(BaseModel):
    """Configure stages how to process images after capture."""

    model_config = ConfigDict(title="Postprocess single captures")

    name: str = Field(
        default="default single image",
        description="Name to identify, only used for display in admin center.",
    )

    jobcontrol: SingleImageJobControl
    processing: SingleImageProcessing
    trigger: Trigger


class CollageConfigurationSet(BaseModel):
    """Configure stages how to process images after capture."""

    model_config = ConfigDict(title="Postprocess collage captures")

    name: str = Field(
        default="default collage",
        description="Name to identify, only used for display in admin center.",
    )

    jobcontrol: MultiImageJobControl
    processing: CollageProcessing
    trigger: Trigger


class AnimationConfigurationSet(BaseModel):
    """Configure stages how to process images after capture."""

    model_config = ConfigDict(title="Postprocess animation captures")

    name: str = Field(
        default="default animation",
        description="Name to identify, only used for display in admin center.",
    )

    jobcontrol: MultiImageJobControl
    processing: AnimationProcessing
    trigger: Trigger


class VideoConfigurationSet(BaseModel):
    """Configure stages how to process images after capture."""

    model_config = ConfigDict(title="Postprocess video captures")

    name: str = Field(
        default="default video",
        description="Name to identify, only used for display in admin center.",
    )

    jobcontrol: VideoJobControl
    processing: VideoProcessing
    trigger: Trigger


class MulticameraConfigurationSet(BaseModel):
    """Configure stages how to process images after capture."""

    model_config = ConfigDict(title="Postprocess multicamera captures")

    name: str = Field(
        default="default wigglegram",
        description="Name to identify, only used for display in admin center.",
    )

    jobcontrol: MulticameraJobControl
    processing: MulticameraProcessing
    trigger: Trigger


class GroupActions(BaseModel):
    """
    Configure actions like capture photo, video, collage and animations.
    """

    model_config = ConfigDict(title="Actions configuration")

    image: list[SingleImageConfigurationSet] = Field(
        default=[
            SingleImageConfigurationSet(
                jobcontrol=SingleImageJobControl(),
                processing=SingleImageProcessing(
                    img_background_enable=True,
                    img_background_file="backgrounds/pink-7761356_1920.jpg",
                    img_frame_enable=True,
                    img_frame_file="frames/frame_image_photobooth-app.png",
                    texts_enable=True,
                    texts=[
                        TextsConfig(
                            text="Visit photobooth-app.org and build yours!",  # use {date} and {time} to add dynamic texts; cannot use in default because tests will fail that compare images
                            pos_x=1300,
                            pos_y=1250,
                            rotate=0,
                            font_size=30,
                            color=Color("#333").as_hex(),
                        )
                    ],
                ),
                trigger=Trigger(
                    ui_trigger=UiTrigger(title="Image", icon="photo_camera"),
                    gpio_trigger=GpioTrigger(pin="27"),
                    keyboard_trigger=KeyboardTrigger(keycode="i"),
                ),
            ),
        ],
        description="Capture single images.",
    )

    collage: list[CollageConfigurationSet] = Field(
        default=[
            CollageConfigurationSet(
                jobcontrol=MultiImageJobControl(
                    ask_approval_each_capture=True,
                    gallery_hide_individual_images=False,
                ),
                processing=CollageProcessing(
                    ask_approval_each_capture=True,
                    canvas_width=1920,
                    canvas_height=1280,
                    merge_definition=[
                        CollageMergeDefinition(
                            description="left",
                            pos_x=160,
                            pos_y=220,
                            width=510,
                            height=725,
                            rotate=0,
                            filter=PilgramFilter.earlybird,
                        ),
                        CollageMergeDefinition(
                            description="middle predefined",
                            pos_x=705,
                            pos_y=66,
                            width=510,
                            height=725,
                            rotate=0,
                            predefined_image="predefined_images/photobooth-collage-predefined-image.png",
                            filter=PilgramFilter.original,
                        ),
                        CollageMergeDefinition(
                            description="right",
                            pos_x=1245,
                            pos_y=220,
                            width=510,
                            height=725,
                            rotate=0,
                            filter=PilgramFilter.reyes,
                        ),
                    ],
                    gallery_hide_individual_images=False,
                    canvas_img_front_enable=True,
                    canvas_img_front_file="frames/pixabay-poster-2871536_1920.png",
                    canvas_texts_enable=True,
                    canvas_texts=[
                        TextsConfig(
                            text="Have a nice day :)",
                            pos_x=200,
                            pos_y=1100,
                            rotate=1,
                            color=Color("#333").as_hex(),
                        )
                    ],
                ),
                trigger=Trigger(
                    ui_trigger=UiTrigger(title="Collage", icon="auto_awesome_mosaic"),
                    gpio_trigger=GpioTrigger(pin="22"),
                    keyboard_trigger=KeyboardTrigger(keycode="c"),
                ),
            )
        ],
        description="Capture collages consist of one or more still images.",
    )

    animation: list[AnimationConfigurationSet] = Field(
        default=[
            AnimationConfigurationSet(
                jobcontrol=MultiImageJobControl(
                    ask_approval_each_capture=False,
                    gallery_hide_individual_images=True,
                    countdown_capture_second_following=0.5,
                ),
                processing=AnimationProcessing(
                    ask_approval_each_capture=False,
                    canvas_width=1500,
                    canvas_height=900,
                    merge_definition=[
                        AnimationMergeDefinition(filter=PilgramFilter.crema),
                        AnimationMergeDefinition(filter=PilgramFilter.inkwell),
                        AnimationMergeDefinition(filter=PilgramFilter.clarendon),
                        AnimationMergeDefinition(filter=PilgramFilter.toaster),
                        AnimationMergeDefinition(
                            duration=4000,
                            filter=PilgramFilter.original,
                            predefined_image="predefined_images/photobooth-gif-animation-predefined-image.png",
                        ),
                    ],
                    gallery_hide_individual_images=True,
                ),
                trigger=Trigger(
                    ui_trigger=UiTrigger(title="Animation", icon="gif_box"),
                    gpio_trigger=GpioTrigger(pin="24"),
                    keyboard_trigger=KeyboardTrigger(keycode="g"),
                ),
            ),
        ],
        description="Capture GIF animation sequence consist of one or more still images. It's not a video but a low number of still images.",
    )

    video: list[VideoConfigurationSet] = Field(
        default=[
            VideoConfigurationSet(
                jobcontrol=VideoJobControl(),
                processing=VideoProcessing(
                    video_duration=5,
                    boomerang=True,
                    video_framerate=15,
                ),
                trigger=Trigger(
                    ui_trigger=UiTrigger(title="Video", icon="movie"),
                    gpio_trigger=GpioTrigger(pin="25"),
                    keyboard_trigger=KeyboardTrigger(keycode="v"),
                ),
            ),
        ],
        description="Capture videos from live streaming backend.",
    )

    multicamera: list[MulticameraConfigurationSet] = Field(
        default=[
            MulticameraConfigurationSet(
                jobcontrol=MulticameraJobControl(),
                processing=MulticameraProcessing(),
                trigger=Trigger(
                    ui_trigger=UiTrigger(title="Wigglegram", icon="burst_mode"),
                    gpio_trigger=GpioTrigger(pin="12"),
                    keyboard_trigger=KeyboardTrigger(keycode="w"),
                ),
            ),
        ],
        description="Capture wigglegrams from a multicamera backend.",
    )
