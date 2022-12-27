from pydantic import ValidationError
from enum import Enum, IntEnum
from pydantic import BaseSettings
from typing import Any
from pathlib import Path
from datetime import datetime
from typing import Annotated
from pydantic import BaseModel, BaseSettings, Field, PrivateAttr
import os
import json
import logging
logger = logging.getLogger(__name__)

CONFIG_FILENAME = "./config/config.json"


class GroupCommon(BaseModel):
    '''Docstring for SubModelCommon'''
    CAPTURE_CAM_RESOLUTION:     tuple[int, int] = (4656, 3496)
    CAPTURE_VIDEO_RESOLUTION:   tuple[int, int] = (1280, 720)
    PREVIEW_CAM_RESOLUTION:     tuple[int, int] = (2328, 1748)
    PREVIEW_VIDEO_RESOLUTION:   tuple[int, int] = (1280, 720)
    LORES_QUALITY:              int = Field(default=80, ge=10, le=100)
    THUMBNAIL_QUALITY:          int = Field(default=60, ge=10, le=100)
    PREVIEW_QUALITY:            int = Field(default=75, ge=10, le=100)
    HIRES_QUALITY:              int = Field(default=90, ge=10, le=100)
    PREVIEW_SCALE_FACTOR:       int = Field(default=25, ge=10, le=100)
    THUMBNAIL_SCALE_FACTOR:     int = Field(default=12.5, ge=10, le=100)

    PREVIEW_PREVIEW_FRAMERATE_DIVIDER: int = Field(default=1, ge=1, le=5)
    EXT_DOWNLOAD_URL: str = Field(
        default="http://dl.qbooth.net/{filename}", description="URL encoded by QR code to download images from onlineservice. {filename} is replaced by actual filename")

    PICAM2_AE_EXPOSURE_MODE: int = Field(
        default=1, ge=0, le=4, description="Usually 0=normal exposure, 1=short, 2=long, 3=custom (not all necessarily supported by camera!")
    # flip camera source horizontal/vertical
    CAMERA_TRANSFORM_HFLIP: bool = False
    CAMERA_TRANSFORM_VFLIP: bool = False

    # autofocus
    # 70 for imx519 (range 0...4000) and 30 for arducam64mp (range 0...1000)
    FOCUSER_ENABLED: bool = True
    FOCUSER_MIN_VALUE: int = 300
    FOCUSER_MAX_VALUE: int = 3000
    FOCUSER_DEF_VALUE: int = 800
    FOCUSER_STEP: int = 50
    # results in max. 1/0.066 fps autofocus speed rate (here about 15fps)
    FOCUSER_MOVE_TIME: float = 0.028
    FOCUSER_JPEG_QUALITY: int = 80
    FOCUSER_ROI: tuple[float, float, float, float] = (
        0.2, 0.2, 0.6, 0.6)  # x, y, width, height in %
    FOCUSER_DEVICE: str = "/dev/v4l-subdev1"
    FOCUSER_REPEAT_TRIGGER: int = 5  # every x seconds trigger autofocus

    PROCESS_COUNTDOWN_TIMER: float = 3
    PROCESS_COUNTDOWN_OFFSET: float = 0.25
    PROCESS_TAKEPIC_MSG: str = "CHEEESE!"
    PROCESS_TAKEPIC_MSG_TIMER: float = 0.5
    PROCESS_AUTOCLOSE_TIMER: int = 10
    PROCESS_ADD_EXIF_DATA: bool = True


class GroupHardwareInput(BaseModel):
    '''Docstring for LocationService'''
    HW_KEYCODE_TAKEPIC: str = "down"


class GroupLocationService(BaseModel):
    '''Docstring for LocationService'''
    LOCATION_SERVICE_ENABLED: bool = False
    LOCATION_SERVICE_API_KEY: str = ""
    LOCATION_SERVICE_CONSIDER_IP: bool = True
    LOCATION_SERVICE_WIFI_INTERFACE_NO: int = 0
    LOCATION_SERVICE_FORCED_UPDATE: int = 60
    # every x minutes
    LOCATION_SERVICE_HIGH_FREQ_UPDATE: int = 10
    # retries after program start to get more accurate data
    LOCATION_SERVICE_THRESHOLD_ACCURATE: int = 1000
    # threshold below which the data is accurate enough to not trigger high freq updates (in meter)


class GroupCamera(BaseModel):
    '''Docstring for GroupCamera'''
    settings: Annotated[str, Field(description="test123")] = 'Bar'


class GroupPersonalize(BaseModel):
    '''Docstring for Personalization'''
    UI_FRONTPAGE_TEXT: str = "Hey! Lets take some pictures! :)"

    GALLERY_ENABLE: bool = True
    GALLERY_EMPTY_MSG: str = "So boring here...🤷‍♂️<br>Let's take some pictures 📷💕"


class GroupDebugging(BaseModel):
    # dont change following defaults. If necessary change via argument
    DEBUG_LEVEL: str = "DEBUG"
    DEBUG_OVERLAY: bool = False


class GroupColorled(BaseModel):
    '''Colorled settings for neopixel and these elements'''
    # infoled / ws2812b ring settings
    NUMBER_LEDS: int = 12
    GPIO_PIN: int = 18
    COLOR: tuple[int, int, int, int] = (255, 255, 255, 255)    # RGBW
    CAPTURE_COLOR: tuple[int, int, int, int] = (0, 125, 125, 0)  # RGBW
    MAX_BRIGHTNESS: int = 50
    ANIMATION_UPDATE: int = 70    # update circle animation every XX ms


class ConfigSettings(BaseModel):
    '''Settings class glueing all together'''

    _processed_at: datetime = PrivateAttr(
        default_factory=datetime.now)  # private attributes

    # groups -> setting items
    common: GroupCommon = GroupCommon()
    camera: GroupCamera = GroupCamera()
    colorled: GroupColorled = GroupColorled()
    debugging: GroupDebugging = GroupDebugging()
    locationservice: GroupLocationService = GroupLocationService()

    def persist(self):
        '''Persist settings to file'''
        logger.debug(f"persist settings to json file")

        with open(CONFIG_FILENAME, "w") as write_file:
            write_file.write(self.json(indent=2))

    def deleteconfig(self):
        '''Reset to defaults'''
        logger.debug(f"settings reset to default")

        try:
            os.remove(CONFIG_FILENAME)
            logger.debug(f"deleted {CONFIG_FILENAME} file.")
        except:
            logger.info(f"delete {CONFIG_FILENAME} file failed.")


# our settings that can be imported throughout the app like # from lib.ConfigService import settings
# TODO: might wanna use LROcache functools.
settings = ConfigSettings()
try:
    with open(CONFIG_FILENAME, "r") as read_file:
        loadedConfig = json.load(read_file)
    settings = ConfigSettings(**loadedConfig)
except FileNotFoundError as e:
    logger.error(
        f"config file {CONFIG_FILENAME} could not be read, using defaults, error {e}")
except ValidationError as e:
    logger.exception(
        f"config file {CONFIG_FILENAME} validation error! program stopped, please fix config {e}")
    quit()


class GroupLogger(BaseModel):

    LOGGER_CONFIG = {
        'version': 1,
        'disable_existing_loggers': False,
        'formatters': {
            'standard': {
                'format': '%(asctime)s [%(levelname)s] %(name)s %(funcName)s() L%(lineno)-4d %(message)s'
            },
            'detailed': {
                'format': '%(asctime)s [%(levelname)s] %(name)s %(funcName)s() L%(lineno)-4d %(message)s call_trace=%(pathname)s L%(lineno)-4d'

            },
        },
        'handlers': {
            'default': {
                'level': 'DEBUG',
                'formatter': 'standard',
                'class': 'logging.StreamHandler',
                # 'stream': 'ext://sys.stdout',  # Default is stderr
            },
            'file': {
                'class': 'logging.handlers.RotatingFileHandler',
                'formatter': 'detailed',
                'filename': './log/qbooth.log',
                'maxBytes': 1024**2,
                'backupCount': 10,
                'level': 'DEBUG',
            },
            'eventstream': {
                'class': '__main__.EventstreamLogHandler',
                'formatter': 'standard',
                'level': 'DEBUG',
            }
        },
        'loggers': {
            '': {  # root logger
                'handlers': ['default', 'eventstream', 'file'],
                'level': 'DEBUG',
                'propagate': False
            },
            '__main__': {  # if __name__ == '__main__'
                'handlers': ['default', 'eventstream', 'file'],
                'level': 'DEBUG',
                'propagate': False
            },
            'picamera2': {
                'handlers': ['default'],
                'level': 'INFO',
                'propagate': False
            },
            'pywifi': {
                'handlers': ['default'],
                'level': 'WARNING',
                'propagate': False
            },
            'sse_starlette.sse': {
                'handlers': ['default'],
                'level': 'INFO',
                'propagate': False
            },
            'lib.Autofocus': {
                'handlers': ['default'],
                'level': 'INFO',
                'propagate': False
            },
            'transitions.core': {
                'handlers': ['default'],
                'level': 'INFO',
                'propagate': False
            },
            'PIL.PngImagePlugin': {
                'handlers': ['default'],
                'level': 'INFO',
                'propagate': False
            },
        }
    }


class ConfigSettingsInternal(BaseModel):
    logger: GroupLogger = GroupLogger()


if __name__ == '__main__':

    settings.debugging.DEBUG_OVERLAY = True
    assert settings.debugging.DEBUG_OVERLAY is True
    settings.persist()
    with open(CONFIG_FILENAME, "r") as read_file:
        loadedConfig = json.load(read_file)
    settings = ConfigSettings(**loadedConfig)  # reread config
    assert settings.debugging.DEBUG_OVERLAY is True

    settings.debugging.DEBUG_OVERLAY = False
    settings.persist()
    with open(CONFIG_FILENAME, "r") as read_file:
        loadedConfig = json.load(read_file)
    settings = ConfigSettings(**loadedConfig)  # reread config
    assert settings.debugging.DEBUG_OVERLAY is False

    settings.debugging.DEBUG_OVERLAY = True
    settings.persist()
    with open(CONFIG_FILENAME, "r") as read_file:
        loadedConfig = json.load(read_file)
    settings = ConfigSettings(**loadedConfig)  # reread config
    assert settings.debugging.DEBUG_OVERLAY is True

    settings.deleteconfig()
    # reread config, this one is default now
    settings = ConfigSettings()
    settings.persist()
    assert settings == ConfigSettings()  # is all default?

    # print(settings)
