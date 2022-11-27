import os
import json
import logging
logger = logging.getLogger(__name__)

CONFIG_FILENAME = "./config/config.json"


class ConfigService(dict):

    def __init__(self, ee):
        # eventbus
        self._ee = ee

        self._current_config =\
            self._default_config = {
                "CAPTURE_CAM_RESOLUTION": (4656, 3496),
                "CAPTURE_VIDEO_RESOLUTION": (1280, 720),
                "PREVIEW_CAM_RESOLUTION": (2328, 1748),
                "PREVIEW_VIDEO_RESOLUTION": (1280, 720),
                "LORES_QUALITY": 80,
                "THUMBNAIL_QUALITY": 60,
                "PREVIEW_QUALITY": 75,
                "HIRES_QUALITY": 90,
                # possible scaling factors (TurboJPEG.scaling_factors)   (nominator, denominator)
                # limitation due to turbojpeg lib usage.
                # ({(13, 8), (7, 4), (3, 8), (1, 2), (2, 1), (15, 8), (3, 4), (5, 8), (5, 4), (1, 1),
                # (1, 8), (1, 4), (9, 8), (3, 2), (7, 8), (11, 8)})
                # example: (1,4) will result in 1/4=0.25=25% down scale in relation to the full resolution picture
                "THUMBNAIL_SCALE_FACTOR": (1, 4),
                "PREVIEW_SCALE_FACTOR": (3, 8),

                "PREVIEW_PREVIEW_FRAMERATE_DIVIDER": 3,

                "EXT_DOWNLOAD_URL": "http://dl.qbooth.net/{filename}",

                # capture
                # Normal/Short(/Long/Custom)
                "CAPTURE_EXPOSURE_MODE": "short",
                "CAMERA_TUNINGFILE": "imx519.json",

                # autofocus
                # 70 for imx519 (range 0...4000) and 30 for arducam64mp (range 0...1000)
                "FOCUSER_ENABLED": True,
                "FOCUSER_MIN_VALUE": 300,
                "FOCUSER_MAX_VALUE": 3000,
                "FOCUSER_DEF_VALUE": 800,
                "FOCUSER_STEP": 50,
                # results in max. 1/0.066 fps autofocus speed rate (here about 15fps)
                "FOCUSER_MOVE_TIME": 0.066,
                "FOCUSER_JPEG_QUALITY": 80,
                "FOCUSER_ROI": (0.2, 0.2, 0.6, 0.6),  # x, y, width, height
                "FOCUSER_DEVICE": "/dev/v4l-subdev1",
                "FOCUSER_REPEAT_TRIGGER": 5,  # every x seconds trigger autofocus

                # dont change following defaults. If necessary change via argument
                "DEBUG_LEVEL": "DEBUG",
                "DEBUG_OVERLAY": False,

                # infoled / ws2812b ring settings
                "WS2812_NUMBER_LEDS": 12,
                "WS2812_GPIO_PIN": 18,
                "WS2812_COLOR": (255, 255, 255, 255),    # RGBW
                "WS2812_CAPTURE_COLOR": (0, 125, 125, 0),  # RGBW
                "WS2812_MAX_BRIGHTNESS": 50,
                "WS2812_ANIMATION_UPDATE": 70,    # update circle animation every XX ms

                # location service
                "LOCATION_SERVICE_ENABLED": False,
                "LOCATION_SERVICE_API_KEY": "",
                "LOCATION_SERVICE_CONSIDER_IP": True,
                "LOCATION_SERVICE_WIFI_INTERFACE_NO": 0,
                "LOCATION_SERVICE_FORCED_UPDATE": 60,  # every x minutes
                # retries after program start to get more accurate data
                "LOCATION_SERVICE_HIGH_FREQ_UPDATE": 10,
                # threshold below which the data is accurate enough to not trigger high freq updates (in meter)
                "LOCATION_SERVICE_THRESHOLD_ACCURATE": 1000,

                "PROCESS_COUNTDOWN_TIMER": 5,
                "PROCESS_COUNTDOWN_OFFSET": 0.5,
                "PROCESS_TAKEPIC_MSG": "CHEEESE!",
                "PROCESS_TAKEPIC_MSG_TIMER": 0.5,
                "PROCESS_AUTOCLOSE_TIMER": 10,

                "POSTPROCESS_OVERLAY_ENABLE": "",
                "POSTPROCESS_OVERLAY_TEXT": "",

                "GALLERY_ENABLE": True,
                "GALLERY_EMPTY_MSG": "So boring here...🤷‍♂️<br>Let's take some pictures 📷💕",


                "HW_KEYCODE_TAKEPIC": None,
                "HW_KEYCODE_TAKEWIGGLEPIC": None,


                "UI_FRONTPAGE_TEXT": "Hey! Lets take some pictures! :)"
            }

        self._internal_config = {
            "LOGGING_CONFIG": {
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
                    },
                    'eventstream': {
                        'class': '__main__.EventstreamLogHandler',
                        'formatter': 'standard',
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
                }
            }
        }

    def reset_default_values(self):
        self._current_config = self._default_config
        self.update_internal_config()

        try:
            os.remove(CONFIG_FILENAME)
        except:
            logger.info("delete settings.json file failed.")

        self._publishSSE_currentconfig()

    def load(self):
        try:
            with open(CONFIG_FILENAME, "r") as read_file:
                import_config = json.load(read_file)
                logger.debug(f"import_config {import_config}")
                self.import_config(import_config)

        except Exception as e:
            logger.exception(e)
            logger.info(f"load settings failed (no file?) {e}")

    def import_config(self, import_config):
        for key in self._default_config:
            # check whether a setting is avail from file and update default
            if key in import_config:
                self._current_config[key] = import_config[key]

        logger.debug(f"_current_config {self._current_config}")

        self.update_internal_config()

        self._ee.emit("config/changed")

        self._publishSSE_currentconfig()

    def update_internal_config(self):
        # map some fields from regular config (default/current) to internal config.
        # internal config is bit more complex and shall not be edited by the user, but its possible to change some values by specific mapping of current_config to internal_config
        if (self._current_config['DEBUG_LEVEL']):
            self._internal_config['LOGGING_CONFIG']['loggers']['']['level'] = self._current_config['DEBUG_LEVEL']
            self._internal_config['LOGGING_CONFIG']['loggers']['__main__']['level'] = self._current_config['DEBUG_LEVEL']

    def save(self):
        logger.debug(f"saving following dict: {self._current_config}")
        with open(CONFIG_FILENAME, "w") as write_file:
            json.dump(self._current_config, write_file, indent=4)

        self._publishSSE_currentconfig()

    def _publishSSEInitial(self):   # TODO, refactor class to make this possible
        self._publishSSE_currentconfig()

    def _publishSSE_currentconfig(self):
        self._ee.emit("publishSSE", sse_event="config/currentconfig",
                      sse_data=json.dumps(self._current_config))
