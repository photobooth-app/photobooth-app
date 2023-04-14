# pylint: disable=line-too-long, too-few-public-methods


"""
ConfigSettings class providing central settings service to app

"""

import os
import json
import logging
from enum import Enum
from typing import Any
from pathlib import Path
from datetime import datetime
import jsonref
from pydantic import BaseModel, BaseSettings, Field, PrivateAttr, Extra

logger = logging.getLogger(__name__)

CONFIG_FILENAME = "./config/config.json"


class EnumDebugLevel(str, Enum):
    """enum for debuglevel"""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"


class GroupCommon(BaseModel):
    """Common settings for photobooth."""

    class Config:
        title = "Common Settings"

    CAPTURE_CAM_RESOLUTION_WIDTH: int = Field(
        default=1280,
        description="still photo camera resolution width on supported backends",
    )
    CAPTURE_CAM_RESOLUTION_HEIGHT: int = Field(
        default=720,
        description="still photo camera resolution height on supported backends",
    )
    PREVIEW_CAM_RESOLUTION_WIDTH: int = Field(
        default=1280,
        description="liveview camera resolution width on supported backends",
    )
    PREVIEW_CAM_RESOLUTION_HEIGHT: int = Field(
        default=720,
        description="liveview camera resolution height on supported backends",
    )
    LIVEVIEW_RESOLUTION_WIDTH: int = Field(
        default=1280,
        description="Liveview resolution width",
    )
    LIVEVIEW_RESOLUTION_HEIGHT: int = Field(
        default=720,
        description="Liveview resolution height",
    )
    LIVEPREVIEW_QUALITY: int = Field(
        default=80,
        ge=10,
        le=100,
        description="Livepreview stream JPEG image quality on supported backends",
        ui_component="QSlider",
    )
    THUMBNAIL_STILL_QUALITY: int = Field(
        default=60,
        ge=10,
        le=100,
        description="Still JPEG thumbnail quality, thumbs used in gallery list",
        ui_component="QSlider",
    )
    PREVIEW_STILL_QUALITY: int = Field(
        default=75,
        ge=10,
        le=100,
        description="Still JPEG preview quality, preview still shown in gallery detail",
        ui_component="QSlider",
    )
    HIRES_STILL_QUALITY: int = Field(
        default=90,
        ge=10,
        le=100,
        description="Still JPEG full resolution quality, applied to download images and images with filter",
        ui_component="QSlider",
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
    DEBUG_LEVEL: EnumDebugLevel = Field(
        title="Debug Level",
        default=EnumDebugLevel.DEBUG,
        description="Log verbosity. File is writte to disc, and latest log is displayed also in UI.",
    )
    LIVEPREVIEW_FRAMERATE: int = Field(
        default=15,
        ge=5,
        le=30,
        description="Reduce the framerate to save cpu/gpu on device displaying the live preview",
        ui_component="QSlider",
    )
    EXT_DOWNLOAD_URL: str = Field(
        default="http://dl.qbooth.net/{filename}",
        description="URL encoded by QR code to download images from onlineservice. {filename} is replaced by actual filename",
    )
    # flip camera source horizontal/vertical
    CAMERA_TRANSFORM_HFLIP: bool = Field(
        default=False,
        description="Apply horizontal flip to image source on supported backends",
    )
    CAMERA_TRANSFORM_VFLIP: bool = Field(
        default=False,
        description="Apply vertical flip to image source on supported backends",
    )
    PROCESS_COUNTDOWN_TIMER: float = Field(
        default=3,
        description="Countdown in seconds, started when user start a capture process",
    )
    PROCESS_COUNTDOWN_OFFSET: float = Field(
        default=0.25,
        description="Trigger capture offset in seconds. 0 trigger exactly when countdown is 0. Triggers the capture offset by the given seconds to compensate for delay in camera.",
    )
    webserver_port: int = Field(
        default=8000,
        description="Port to serve the photobooth website. Ensure the port is available.",
    )


class EnumImageBackendsMain(str, Enum):
    """enum to choose image backend MAIN from"""

    IMAGESERVER_SIMULATED = "ImageServerSimulated"
    IMAGESERVER_PICAM2 = "ImageServerPicam2"
    IMAGESERVER_WEBCAMCV2 = "ImageServerWebcamCv2"
    IMAGESERVER_WEBCAMV4L = "ImageServerWebcamV4l"
    IMAGESERVER_GPHOTO2 = "ImageServerGphoto2"
    # Not yet finished backends:
    # ImageServerDigicamcontrol = 'ImageServerDigicamcontrol'


class EnumImageBackendsLive(str, Enum):
    """enum to choose image backend LIVE from"""

    NULL = None
    IMAGESERVER_SIMULATED = "ImageServerSimulated"
    IMAGESERVER_WEBCAMCV2 = "ImageServerWebcamCv2"
    IMAGESERVER_WEBCAMV4L = "ImageServerWebcamV4l"


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

    class Config:
        title = "Camera Backend Settings"

    MAIN_BACKEND: EnumImageBackendsMain = Field(
        title="Main Backend",
        default=EnumImageBackendsMain.IMAGESERVER_SIMULATED,
        description="Main backend to use for high quality still captures. Also used for livepreview if backend is capable of.",
    )
    LIVE_BACKEND: EnumImageBackendsLive = Field(
        title="Live Backend",
        default=None,
        description="Secondary backend used for live streaming only. Useful to stream from webcam if DSLR camera has no livestream capability.",
    )
    LIVEPREVIEW_ENABLED: bool = Field(
        default=True, description="Enable livestream (if possible)"
    )

    cv2_device_index: int = Field(
        default=0, description="Device index of webcam opened in cv2 backend"
    )
    v4l_device_index: int = Field(
        default=0, description="Device index of webcam opened in v4l backend"
    )

    picam2_AE_EXPOSURE_MODE: int = Field(
        default=1,
        ge=0,
        le=4,
        description="Usually 0=normal exposure, 1=short, 2=long, 3=custom. Not all necessarily supported by camera!",
    )

    picam2_focuser_module: EnumFocuserModule = Field(
        title="Picam2 Focuser Module",
        default=EnumFocuserModule.NULL,
        description="Choose continuous or interval mode to trigger autofocus of picamera2 cam.",
    )

    picam2_stream_quality: EnumPicamStreamQuality = Field(
        title="Picam2 Stream Quality (for livepreview)",
        default=EnumPicamStreamQuality.MEDIUM,
        description="Lower quality results in less data to be transferred and may reduce load on display device.",
    )

    picam2_focuser_interval: int = Field(
        default=10,
        description="Every x seconds trigger autofocus",
    )


class GroupHardwareInput(BaseModel):
    """Configure GPIO, keyboard and more."""

    class Config:
        title = "Hardware Input/Output Settings"

    keyboard_input_enabled: bool = Field(
        default=False,
        description="Enable keyboard input globally",
    )
    keyboard_input_keycode_takepic: str = Field(
        default="down",
        description="Keycode triggers capture of one image",
    )


class GroupUiSettings(BaseModel):
    """Personalize the booth's UI."""

    class Config:
        title = "Personalize the User Interface"

    FRONTPAGE_TEXT: str = Field(
        default='<div class="fixed-center text-h2 text-weight-bold text-center text-white" style="text-shadow: 4px 4px 4px #666;">Hey!<br>Let\'s take some pictures <br>📷💕</div>',
        description="Text/HTML displayed on frontpage.",
    )
    GALLERY_ENABLE: bool = Field(
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
        default=15,
        description="Timeout in seconds a new item popup closes automatically.",
    )
    SHOW_ADMIN_LINK_ON_FRONTPAGE: bool = Field(
        default=True,
        description="Show link to admin center, usually only during setup.",
    )


class GroupWled(BaseModel):
    """
    WLED integration for countdown led / shoot animation
    needs WLED module connected via USB serial port and
    three presets:
    1: standby (usually LEDs off)
    2: countdown (animates countdown)
    3: shoot (imitate a flash)
    Please define presets on your own in WLED webfrontend
    """

    class Config:
        title = "WLED Integration Settings"

    # WledService settings
    ENABLED: bool = Field(
        default=False,
        description="Enable WLED integration for user feedback during countdown and capture by LEDs.",
    )
    SERIAL_PORT: str = Field(
        default="",
        description="Serial port the WLED device is connected to.",
    )


class GroupMisc(BaseModel):
    """
    Quite advanced, usually not necessary to touch.
    """

    class Config:
        title = "Miscellaneous Settings"

    # WledService settings
    photoboothproject_image_directory: str = Field(
        default="/var/www/html/data/tmp/",
        description="Photoboothproject compatibility setting. Provide the directory, where photobooth expects the image to be created. Needed for safety.",
    )


def json_config_settings_source(_settings: BaseSettings) -> dict[str, Any]:
    """
    custom parser to read json config file
    """
    encoding = _settings.__config__.env_file_encoding
    json_config = {}
    try:
        json_config = json.loads(Path(CONFIG_FILENAME).read_text(encoding))
    except FileNotFoundError:
        # ignore file not found, because it could have been deleted or not yet initialized
        # using defaults
        pass

    return json_config


class ConfigSettings(BaseSettings):
    """
    Settings class glueing all together

    In the case where a value is specified for the same Settings field in multiple ways, the selected value is determined as follows (in descending order of priority):

    1 Arguments passed to the Settings class initialiser.
    2 Environment variables, e.g. my_prefix_special_function as described above.
    3 Variables loaded from a dotenv (.env) file.
    4 Variables loaded from the secrets directory.
    5 The default field values for the Settings model.
    """

    _processed_at: datetime = PrivateAttr(
        default_factory=datetime.now
    )  # private attributes

    # size of shared memory to transfer images between backend and app. needs to be as large as largest image to be transferred
    # 15MB should be sufficient, might change in future
    _shared_memory_buffer_size: int = PrivateAttr(default=15 * 1024**2)

    # groups -> setting items
    common: GroupCommon = GroupCommon()
    uisettings: GroupUiSettings = GroupUiSettings()
    backends: GroupBackends = GroupBackends()
    wled: GroupWled = GroupWled()
    hardwareinput: GroupHardwareInput = GroupHardwareInput()
    misc: GroupMisc = GroupMisc()

    # make it a singleton: https://stackoverflow.com/a/1810367
    def __new__(cls, *args, **kwargs):
        if not hasattr(cls, "_instance"):
            cls._instance = super(ConfigSettings, cls).__new__(cls, *args, **kwargs)
        return cls._instance

    class Config:
        """
        pydantic config class modified
        """

        env_file_encoding = "utf-8"
        # first in following list is least important; last .env file overwrites the other.
        env_file = ".env.installer", ".env.dev", ".env.prod"
        env_nested_delimiter = "__"
        case_sensitive = True
        extra = Extra.ignore

        @classmethod
        def customise_sources(
            cls,
            init_settings,
            env_settings,
            file_secret_settings,
        ):
            """customize sources"""
            return (
                init_settings,
                json_config_settings_source,
                env_settings,
                file_secret_settings,
            )

    def get_schema(self, schema_type: str = "default"):
        """Get schema to build UI. Schema is polished to the needs of UI"""
        if schema_type == "dereferenced":
            # https://github.com/pydantic/pydantic/issues/889#issuecomment-1064688675
            return jsonref.loads(settings.schema_json())

        return settings.schema()

    def persist(self):
        """Persist settings to file"""
        logger.debug("persist settings to json file")

        with open(CONFIG_FILENAME, mode="w", encoding="utf-8") as write_file:
            write_file.write(self.json(indent=2))

    def deleteconfig(self):
        """Reset to defaults"""
        logger.debug("settings reset to default")

        try:
            os.remove(CONFIG_FILENAME)
            logger.debug(f"deleted {CONFIG_FILENAME} file.")
        except (FileNotFoundError, PermissionError):
            logger.info(f"delete {CONFIG_FILENAME} file failed.")


# our settings that can be imported throughout the app like # from src.ConfigService import settings
settings = ConfigSettings()
