"""
AppConfig class providing central config

"""

import json
import logging
import os
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

import jsonref
from pydantic import BaseModel, ConfigDict, Field, PrivateAttr
from pydantic.fields import FieldInfo
from pydantic_extra_types.color import Color
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
)

logger = logging.getLogger(__name__)

CONFIG_FILENAME = "./config/config.json"


class EnumDebugLevel(str, Enum):
    """enum for debuglevel"""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"


class GroupCommon(BaseModel):
    """Common config for photobooth."""

    model_config = ConfigDict(title="Common Config")

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
        default=900,
        ge=200,
        le=2000,
        description="Width of resized preview image, height is automatically calculated to keep aspect ratio",
    )
    THUMBNAIL_STILL_WIDTH: int = Field(
        default=400,
        ge=100,
        le=1000,
        description="Width of resized thumbnail image, height is automatically calculated to keep aspect ratio",
    )

    LIVEPREVIEW_FRAMERATE: int = Field(
        default=15,
        ge=5,
        le=30,
        description="Reduce the framerate to save cpu/gpu on device displaying the live preview",
        json_schema_extra={"ui_component": "QSlider"},
    )

    countdown_capture_first: float = Field(
        default=1,
        description="Countdown in seconds, started when user start a capture process",
    )

    countdown_capture_second_following: float = Field(
        default=0.2,
        description="Countdown in seconds, used for second and following captures for collages",
    )
    countdown_cheese_message_offset: float = Field(
        default=0.5,
        description="Offset display cheese message before 0 would be reached (in seconds). Bigger or equal than camera capture offset.",
    )
    countdown_camera_capture_offset: float = Field(
        default=0.25,
        description="Trigger camera capture by offset earlier (in seconds). 0 trigger exactly when countdown is 0. Use to compensate for delay in camera processing for better UX.",
    )

    collage_automatic_capture_continue: bool = Field(
        default=True,
        description="Automatically continue with second and following images to capture for collage. No user interaction in between.",
    )

    DEBUG_LEVEL: EnumDebugLevel = Field(
        title="Debug Level",
        default=EnumDebugLevel.DEBUG,
        description="Log verbosity. File is writte to disc, and latest log is displayed also in UI.",
    )

    webserver_bind_ip: str = Field(
        default="0.0.0.0",
        description="IP/Hostname to bind the webserver to. 0.0.0.0 means bind to all IP adresses of host.",
    )
    webserver_port: int = Field(
        default=8000,
        description="Port to serve the photobooth website. Ensure the port is available.",
    )

    shareservice_enabled: bool = Field(
        default=False,
        description="Enable share service. To enable URL needs to be configured and dl.php script setup properly.",
    )
    shareservice_url: str = Field(
        default="https://explain-shareservice.photobooth-app.de/dl.php",
        description="URL of php script that is used to serve files and share via QR code.",
    )
    shareservice_apikey: str = Field(
        default="changedefault!",
        description="Key to secure the download php script. Set the key in dl.php script to same value. Only if correct key is provided the shareservice works properly.",
    )
    shareservice_share_original: bool = Field(
        default=False,
        description="Upload original image as received from camera. If unchecked, the full processed version is uploaded with filter and texts applied.",
    )


class EnumImageBackendsMain(str, Enum):
    """enum to choose image backend MAIN from"""

    SIMULATED = "Simulated"
    PICAMERA2 = "Picamera2"
    WEBCAMCV2 = "WebcamCv2"
    WEBCAMV4L = "WebcamV4l"
    GPHOTO2 = "Gphoto2"
    # Not yet finished backends:
    # Digicamcontrol = 'Digicamcontrol'


class EnumImageBackendsLive(str, Enum):
    """enum to choose image backend LIVE from"""

    DISABLED = "Disabled"
    SIMULATED = "Simulated"
    PICAMERA2 = "Picamera2"
    WEBCAMCV2 = "WebcamCv2"
    WEBCAMV4L = "WebcamV4l"


class EnumFocuserModule(str, Enum):
    """List to choose focuser module from"""

    NULL = None
    LIBCAM_AF_CONTINUOUS = "LibcamAfContinuous"
    LIBCAM_AF_INTERVAL = "LibcamAfInterval"


class EnumPicamStreamQuality(str, Enum):
    """Enum type to describe the quality wanted from an encoder.
    This may be passed if a specific value (such as bitrate) has not been set.
    """

    VERY_LOW = "very low"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    VERY_HIGH = "very high"


class GroupBackends(BaseModel):
    """
    Choose backends for still images/high quality images captured on main backend.
    If the livepreview is enabled, the video is captured from live backend (if configured)
    or main backend.
    """

    model_config = ConfigDict(title="Camera Backend Config")

    MAIN_BACKEND: EnumImageBackendsMain = Field(
        title="Main Backend",
        default=EnumImageBackendsMain.SIMULATED,
        description="Main backend to use for high quality still captures. Also used for livepreview if backend is capable of.",
    )
    LIVE_BACKEND: EnumImageBackendsLive = Field(
        title="Live Backend",
        default=EnumImageBackendsLive.DISABLED,
        description="Secondary backend used for live streaming only. Useful to stream from webcam if DSLR camera has no livestream capability.",
    )
    LIVEPREVIEW_ENABLED: bool = Field(
        default=True,
        description="Enable livestream (if possible)",
    )

    cv2_CAM_RESOLUTION_WIDTH: int = Field(
        default=10000,
        description="still photo camera resolution width to opencv2 backend",
    )
    cv2_CAM_RESOLUTION_HEIGHT: int = Field(
        default=10000,
        description="still photo camera resolution height to opencv2 backend",
    )
    cv2_device_index: int = Field(
        default=0,
        description="Device index of webcam opened in cv2 backend",
    )
    cv2_CAMERA_TRANSFORM_HFLIP: bool = Field(
        default=False,
        description="Apply horizontal flip to image source to opencv2 backend",
    )
    cv2_CAMERA_TRANSFORM_VFLIP: bool = Field(
        default=False,
        description="Apply vertical flip to image source to opencv2 backend",
    )

    v4l_CAM_RESOLUTION_WIDTH: int = Field(
        default=10000,
        description="still photo camera resolution width on supported backends",
    )
    v4l_CAM_RESOLUTION_HEIGHT: int = Field(
        default=10000,
        description="still photo camera resolution height on supported backends",
    )
    v4l_device_index: int = Field(
        default=0,
        description="Device index of webcam opened in v4l backend",
    )

    gphoto2_disable_viewfinder_before_capture: bool = Field(
        default=True,
        description="Disable viewfinder before capture might speed up following capture autofocus. Might not work with every camera.",
    )

    gphoto2_wait_event_after_capture_trigger: bool = Field(
        default=False,
        description="Usually wait_for_event not necessary before downloading the file from camera. Adjust if necessary.",
    )

    picamera2_CAPTURE_CAM_RESOLUTION_WIDTH: int = Field(
        default=1280,
        description="still photo camera resolution width on supported backends",
    )
    picamera2_CAPTURE_CAM_RESOLUTION_HEIGHT: int = Field(
        default=720,
        description="still photo camera resolution height on supported backends",
    )
    picamera2_PREVIEW_CAM_RESOLUTION_WIDTH: int = Field(
        default=1280,
        description="liveview camera resolution width on supported backends",
    )
    picamera2_PREVIEW_CAM_RESOLUTION_HEIGHT: int = Field(
        default=720,
        description="liveview camera resolution height on supported backends",
    )
    picamera2_LIVEVIEW_RESOLUTION_WIDTH: int = Field(
        default=1280,
        description="Liveview resolution width",
    )
    picamera2_LIVEVIEW_RESOLUTION_HEIGHT: int = Field(
        default=720,
        description="Liveview resolution height",
    )
    picamera2_CAMERA_TRANSFORM_HFLIP: bool = Field(
        default=False,
        description="Apply horizontal flip to image source to picamera2 backend",
    )
    picamera2_CAMERA_TRANSFORM_VFLIP: bool = Field(
        default=False,
        description="Apply vertical flip to image source to picamera2 backend",
    )
    picamera2_AE_EXPOSURE_MODE: int = Field(
        default=1,
        ge=0,
        le=4,
        description="Usually 0=normal exposure, 1=short, 2=long, 3=custom. Not all necessarily supported by camera!",
    )
    picamera2_focuser_module: EnumFocuserModule = Field(
        title="Picamera2 Focuser Module",
        default=EnumFocuserModule.NULL,
        description="Choose continuous or interval mode to trigger autofocus of picamera2 cam.",
    )
    picamera2_stream_quality: EnumPicamStreamQuality = Field(
        title="Picamera2 Stream Quality (for livepreview)",
        default=EnumPicamStreamQuality.MEDIUM,
        description="Lower quality results in less data to be transferred and may reduce load on display device.",
    )
    picamera2_focuser_interval: int = Field(
        default=10,
        description="Every x seconds trigger autofocus",
    )


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


class TextStageConfig(BaseModel):
    text: str = ""
    pos_x: int = 50
    pos_y: int = 50
    # rotate: int = 0 # TODO: not yet implemented
    font_size: int = 20
    font: str = "Roboto-Bold.ttf"
    color: Color = Color("red").as_named()


class CollageStageConfig(BaseModel):
    pos_x: int = 50
    pos_y: int = 50
    width: int = 600
    height: int = 400
    rotate: int = 0
    predefined_image: str = ""


class GroupMediaprocessing(BaseModel):
    """Configure stages how to process images after capture."""

    model_config = ConfigDict(title="Process media after capture")

    pic1_pipeline_enable: bool = Field(
        default=False,
        description="Enable/Disable 1pic processing pipeline completely",
    )

    pic1_filter: EnumPilgramFilter = Field(
        title="Pic1 Filter",
        default=EnumPilgramFilter.original,
        description="Instagram-like filter to apply per default. 'original' applies no filter.",
    )

    pic1_text_overlay_enable: bool = Field(
        default=False,
        description="General enable apply texts below.",
    )
    pic1_text_overlay: list[TextStageConfig] = Field(
        default=[],
        description="Text to overlay on images after capture. Pos_x/Pos_y measure in pixel starting 0/0 at top-left in image. Font to use in text stages. File needs to be located in DATA_DIR/*",
    )

    pic1_removechromakey_enable: bool = Field(
        default=False,
        description="Apply chromakey greenscreen removal from captured images",
    )
    pic1_removechromakey_keycolor: int = Field(
        default=110,
        ge=0,
        le=360,
        description="Color (H) in HSV colorspace to remove on 360° scale.",
    )
    pic1_removechromakey_tolerance: int = Field(
        default=10,
        ge=1,
        le=50,
        description="Tolerance for color (H) on chromakey color removal.",
    )

    pic1_fill_background_enable: bool = Field(
        default=False,
        description="Apply solid color background to captured image (useful only if image is extended or background removed)",
    )
    pic1_fill_background_color: Color = Field(
        default=Color("blue"),
        description="Solid color used to fill background.",
    )

    pic1_img_background_enable: bool = Field(
        default=False,
        description="Add image from file to background (useful only if image is extended or background removed)",
    )
    pic1_img_background_file: str = Field(
        default="pink-7761356_1920.png",
        description="Image file to use as background filling transparent area. File needs to be located in DATA_DIR/*",
    )

    collage_merge_definition: list[CollageStageConfig] = Field(
        default=[
            CollageStageConfig(pos_x=50),
            CollageStageConfig(pos_x=700),
            CollageStageConfig(pos_x=50, pos_y=500),
            CollageStageConfig(pos_x=700, pos_y=500, rotate=5),
        ],
        description="How to arrange single images in the collage. Pos_x/Pos_y measure in pixel starting 0/0 at top-left in image. Width/Height in pixels. Aspect ratio is kept always. Predefined image files are used instead a camera capture. File needs to be located in DATA_DIR/*",
    )


class GroupHardwareInputOutput(BaseModel):
    """
    Configure hardware GPIO, keyboard and more. Find integration information in the documentation.
    """

    model_config = ConfigDict(title="Hardware Input/Output Config")

    # keyboardservice config
    keyboard_input_enabled: bool = Field(
        default=False,
        description="Enable keyboard input globally",
    )
    keyboard_input_keycode_takepic: str = Field(
        default="i",
        description="Keycode triggers capture of one image",
    )
    keyboard_input_keycode_takecollage: str = Field(
        default="c",
        description="Keycode triggers capture of collage",
    )
    keyboard_input_keycode_print_recent_item: str = Field(
        default="p",
        description="Keycode triggers printing most recent image captured",
    )

    # WledService Config
    wled_enabled: bool = Field(
        default=False,
        description="Enable WLED integration for user feedback during countdown and capture by LEDs.",
    )
    wled_serial_port: str = Field(
        default="",
        description="Serial port the WLED device is connected to.",
    )

    # GpioService Config
    gpio_enabled: bool = Field(
        default=False,
        description="Enable Raspberry Pi GPIOzero integration.",
    )
    gpio_pin_shutdown: int = Field(
        default=17,
        description="GPIO pin to shutdown after holding it for 2 seconds.",
    )
    gpio_pin_reboot: int = Field(
        default=18,
        description="GPIO pin to reboot after holding it for 2 seconds.",
    )
    gpio_pin_take1pic: int = Field(
        default=27,
        description="GPIO pin to take one picture.",
    )
    gpio_pin_collage: int = Field(
        default=22,
        description="GPIO pin to take a collage.",
    )
    gpio_pin_print_recent_item: int = Field(
        default=23,
        description="GPIO pin to print last captured item.",
    )

    # PrintingService Config
    printing_enabled: bool = Field(
        default=False,
        description="Enable printing in general.",
    )
    printing_command: str = Field(
        default="mspaint /p {filename}",
        description="Command issued to print. Use {filename} as placeholder for the JPEG image to be printed.",
    )
    printing_blocked_time: int = Field(
        default=20,
        description="Block queue print until time is passed. Time in seconds.",
    )


class GroupUiSettings(BaseModel):
    """Personalize the booth's UI."""

    model_config = ConfigDict(title="Personalize the User Interface")

    FRONTPAGE_TEXT: str = Field(
        default='<div class="fixed-center text-h2 text-weight-bold text-center text-white" style="text-shadow: 4px 4px 4px #666;">Hey!<br>Let\'s take some pictures <br>📷💕</div>',
        description="Text/HTML displayed on frontpage.",
    )
    GALLERY_ENABLED: bool = Field(
        default=True,
        description="Enable gallery for user.",
    )
    GALLERY_EMPTY_MSG: str = Field(
        default="So boring here...🤷‍♂️<br>Let's take some pictures 📷💕",
        description="Message displayed if gallery is empty.",
    )
    TAKEPIC_MSG: str = Field(
        default="CHEEESE!",
        description="Message shown during capture. Use icons also.",
    )
    TAKEPIC_MSG_TIME: float = Field(
        default=0.5,
        description="Offset in seconds, the message above shall be shown.",
    )
    AUTOCLOSE_NEW_ITEM_ARRIVED: int = Field(
        default=30,
        description="Timeout in seconds a new item popup closes automatically.",
    )
    SHOW_ADMIN_LINK_ON_FRONTPAGE: bool = Field(
        default=True,
        description="Show link to admin center, usually only during setup.",
    )
    gallery_show_filter: bool = Field(
        default=True,
        description="",
    )
    gallery_filter_userselectable: list[EnumPilgramFilter] = Field(
        title="Pic1 Filter Userselectable",
        default=[EnumPilgramFilter.original, EnumPilgramFilter.clarendon, EnumPilgramFilter.moon],
        description="Filter the user may choose from in the gallery. 'original' applies no filter.",
    )
    gallery_show_download: bool = Field(
        default=True,
        description="",
    )
    gallery_show_delete: bool = Field(
        default=True,
        description="",
    )
    gallery_show_print: bool = Field(
        default=True,
        description="",
    )


class GroupMisc(BaseModel):
    """
    Quite advanced, usually not necessary to touch.
    """

    model_config = ConfigDict(title="Miscellaneous Config")


class JsonConfigSettingsSource(PydanticBaseSettingsSource):
    """
    A simple settings source class that loads variables from a JSON file
    at the project's root.

    Here we happen to choose to use the `env_file_encoding` from Config
    when reading `config.json`
    """

    def get_field_value(self, field: FieldInfo, field_name: str) -> tuple[Any, str, bool]:
        encoding = self.config.get("env_file_encoding")
        field_value = None
        try:
            file_content_json = json.loads(Path(CONFIG_FILENAME).read_text(encoding))
            field_value = file_content_json.get(field_name)
        except FileNotFoundError:
            # ignore file not found, because it could have been deleted or not yet initialized
            # using defaults
            pass

        return field_value, field_name, False

    def prepare_field_value(self, field_name: str, field: FieldInfo, value: Any, value_is_complex: bool) -> Any:
        return value

    def __call__(self) -> dict[str, Any]:
        d: dict[str, Any] = {}

        for field_name, field in self.settings_cls.model_fields.items():
            field_value, field_key, value_is_complex = self.get_field_value(field, field_name)
            field_value = self.prepare_field_value(field_name, field, field_value, value_is_complex)
            if field_value is not None:
                d[field_key] = field_value

        return d


class AppConfig(BaseSettings):
    """
    AppConfig class glueing all together

    In the case where a value is specified for the same Settings field in multiple ways, the selected value is determined as follows (in descending order of priority):

    1 Arguments passed to the Settings class initialiser.
    2 Environment variables, e.g. my_prefix_special_function as described above.
    3 Variables loaded from a dotenv (.env) file.
    4 Variables loaded from the secrets directory.
    5 The default field values for the Settings model.
    """

    _processed_at: datetime = PrivateAttr(default_factory=datetime.now)  # private attributes

    # groups -> setting items
    common: GroupCommon = GroupCommon()
    mediaprocessing: GroupMediaprocessing = GroupMediaprocessing()
    uisettings: GroupUiSettings = GroupUiSettings()
    backends: GroupBackends = GroupBackends()
    hardwareinputoutput: GroupHardwareInputOutput = GroupHardwareInputOutput()
    misc: GroupMisc = GroupMisc()

    # TODO[pydantic]: We couldn't refactor this class, please create the `model_config` manually.
    # Check https://docs.pydantic.dev/dev-v2/migration/#changes-to-config for more information.
    model_config = SettingsConfigDict(
        env_file_encoding="utf-8",
        # first in following list is least important; last .env file overwrites the other.
        env_file=[".env.installer", ".env.dev", ".env.test", ".env.prod"],
        env_nested_delimiter="__",
        case_sensitive=True,
        extra="ignore",
    )

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        """customize sources"""
        return (
            init_settings,
            JsonConfigSettingsSource(settings_cls),
            dotenv_settings,
            env_settings,
            file_secret_settings,
        )

    def get_schema(self, schema_type: str = "default"):
        """Get schema to build UI. Schema is polished to the needs of UI"""
        if schema_type == "dereferenced":
            # https://github.com/pydantic/pydantic/issues/889#issuecomment-1064688675
            return jsonref.loads(json.dumps(self.model_json_schema()))

        return self.model_json_schema()

    def persist(self):
        """Persist config to file"""
        logger.debug("persist config to json file")

        with open(CONFIG_FILENAME, mode="w", encoding="utf-8") as write_file:
            write_file.write(self.model_dump_json(indent=2))

    def deleteconfig(self):
        """Reset to defaults"""
        logger.debug("config reset to default")

        try:
            os.remove(CONFIG_FILENAME)
            logger.debug(f"deleted {CONFIG_FILENAME} file.")
        except (FileNotFoundError, PermissionError):
            logger.info(f"delete {CONFIG_FILENAME} file failed.")
