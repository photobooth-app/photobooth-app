# Simple test for NeoPixels on Raspberry Pi
# import board
# import neopixel
from .ConfigSettings import settings
import time
from lib.StoppableThread import StoppableThread
import logging
from pymitter import EventEmitter
logger = logging.getLogger(__name__)

enable = False
try:
    from rpi_ws281x import PixelStrip, Color, WS2812_STRIP

    # LED strip configuration:
    LED_FREQ_HZ = 800000  # LED signal frequency in hertz (usually 800khz)
    LED_DMA = 10          # DMA channel to use for generating signal (try 10)
    # True to invert the signal (when using NPN transistor level shift)
    LED_INVERT = False
    LED_CHANNEL = 0       # set to '1' for GPIOs 13, 19, 41, 45 or 53
    LED_STRIP_TYPE = WS2812_STRIP  # or WS2811_STRIP_GRB

    enable = True and settings.colorled.ENABLED
except ModuleNotFoundError as e:
    logger.error(
        "module only avail on rpi; disabled module because not avail.")
    logger.error(e)

    # polyfill for color to make the app work even if module not avail
    def Color(a, b, c, d=''):
        pass


class InfoLed():
    def __init__(self, ee: EventEmitter, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs

        if not enable == True:
            logger.info("infoled module disabled")
            return

        self._ee = ee
        self._ee.on("statemachine/armed", self.startCountdown)
        self._ee.on("frameserver/onCapture", self.captureStart)
        self._ee.on("frameserver/onCaptureFinished", self.captureFinished)

        self._countdownAnimationThread = StoppableThread(name="countdownAnimationThread",
                                                         target=self._countdownAnimationFun, daemon=True)

        self._pixels = PixelStrip(settings.colorled.NUMBER_LEDS, settings.colorled.GPIO_PIN, LED_FREQ_HZ,
                                  LED_DMA, LED_INVERT, settings.colorled.MAX_BRIGHTNESS, LED_CHANNEL, LED_STRIP_TYPE)
        self._pixels.begin()
        self._fill(Color(0, 0, 0))

    def _fill(self, color=Color(0, 0, 0)):
        for i in range(self._pixels.numPixels()):
            self._pixels.setPixelColor(i, color)
        self._pixels.show()

    def _countdownAnimationFun(self):
        """Loading circle animation"""
        color = Color(
            settings.colorled.COLOR[0], settings.colorled.COLOR[1], settings.colorled.COLOR[2], settings.colorled.COLOR[3])
        colorarray = [color >> 16 &
                      255, color >> 8 & 255, color >> 0 & 255, color >> 24 & 255]  # RGBW
        # print(colorarray)

        while not self._countdownAnimationThread.stopped():  # repeat until stopped
            for i in range(0, self._pixels.numPixels()):
                self._pixels.setPixelColor(
                    (i+3) % 12, Color(colorarray[0], colorarray[1], colorarray[2], colorarray[3]))
                self._pixels.setPixelColor(
                    (i+2) % 12, Color(colorarray[0] >> 2, colorarray[1] >> 2, colorarray[2] >> 2, colorarray[3] >> 2))
                self._pixels.setPixelColor(
                    (i+1) % 12, Color(colorarray[0] >> 4, colorarray[1] >> 4, colorarray[2] >> 4, colorarray[3] >> 4))
                self._pixels.setPixelColor((i+0) % 12, 0)
                self._pixels.show()

                # in between check to abort animation if stop requested during run
                if (self._countdownAnimationThread.stopped()):
                    break

                time.sleep(
                    settings.colorled.ANIMATION_UPDATE / 1000.0)

        # turn off all led when countdown ends
        self._fill(Color(0, 0, 0))

    def startCountdown(self):
        self._countdownAnimationThread = StoppableThread(name="countdownAnimationThread",
                                                         target=self._countdownAnimationFun, daemon=True)

        self._countdownAnimationThread.start()

    def stopCountdown(self):
        if self._countdownAnimationThread.is_alive():
            self._countdownAnimationThread.stop()
            self._countdownAnimationThread.join(
                ((settings.colorled.ANIMATION_UPDATE+50) / 1000.0))   # wait one update run longest, afterwards continue...

        self._fill(Color(0, 0, 0))

    def captureStart(self):
        self.stopCountdown()
        self._fill(Color(
            settings.colorled.CAPTURE_COLOR[0], settings.colorled.CAPTURE_COLOR[1], settings.colorled.CAPTURE_COLOR[2], settings.colorled.CAPTURE_COLOR[3]))

    def captureFinished(self):
        self.stopCountdown()
        self._fill(Color(0, 0, 0))
