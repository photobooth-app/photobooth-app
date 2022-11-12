from rpi_ws281x import Color
import logging
from libcamera import controls


class CONFIG():
    # debugging
    DEBUG_LOGFILE = False
    LOGGING_LEVEL = logging.DEBUG

    # quality
    MAIN_RESOLUTION_REDUCE_FACTOR = 1
    LORES_RESOLUTION = (1280, 720)
    LORES_QUALITY = 80
    HIRES_QUALITY = 90

    # location service
    LOCATION_SERVICE_API_KEY = "AIzaSyCzOzWNecM2ysPJjrSHW18YyM0DC0ot0QQ"
    LOCATION_SERVICE_CONSIDER_IP = True
    LOCATION_SERVICE_WIFI_INTERFACE_NO = 0
    LOCATION_SERVICE_FORCED_UPDATE = 60  # every x minutes
    # retries after program start to get more accurate data
    LOCATION_SERVICE_HIGH_FREQ_UPDATE = 10
    # threshold below which the data is accurate enough to not trigger high freq updates (in meter)
    LOCATION_SERVICE_THRESHOLD_ACCURATE = 1000

    # capture
    CAPTURE_EXPOSURE_MODE = controls.AeExposureModeEnum.Short

    # autofocus
    # 70 for imx519 (range 0...4000) and 30 for arducam64mp (range 0...1000)
    FOCUSER_MIN_VALUE = 0
    FOCUSER_MAX_VALUE = 4000
    FOCUSER_DEF_VALUE = 400
    FOCUSER_STEP = 50
    FOCUSER_MOVE_TIME = 0.066
    FOCUSER_JPEG_QUALITY = 85
    FOCUSER_ROI = (0.2, 0.2, 0.6, 0.6)  # x, y, width, height
    FOCUSER_DEVICE = "/dev/v4l-subdev1"
    FOCUSER_REPEAT_TRIGGER = 5  # every x seconds trigger autofocus

    # dont change following defaults. If necessary change via argument
    DEBUG = False
    DEBUG_SHOWPREVIEW = False

    # infoled / ws2812b ring settings
    WS2812_NUMBER_LEDS = 12
    WS2812_GPIO_PIN = 18
    WS2812_COLOR = Color(255, 255, 255)
    WS2812_CAPTURE_COLOR = Color(0, 125, 125)
    WS2812_MAX_BRIGHTNESS = 50
    WS2812_ANIMATION_UPDATE = 70    # update circle animation every XX ms
