# Simple test for NeoPixels on Raspberry Pi
#import board
#import neopixel
import time
from lib.StoppableThread import StoppableThread
import time
from rpi_ws281x import PixelStrip, Color, WS2812_STRIP

# LED strip configuration:
LED_FREQ_HZ = 800000  # LED signal frequency in hertz (usually 800khz)
LED_DMA = 10          # DMA channel to use for generating signal (try 10)
# True to invert the signal (when using NPN transistor level shift)
LED_INVERT = False
LED_CHANNEL = 0       # set to '1' for GPIOs 13, 19, 41, 45 or 53
LED_STRIP_TYPE = WS2812_STRIP  # or WS2811_STRIP_GRB


class InfoLed():
    def __init__(self, CONFIG, notifier, *args, **kwargs):
        self._CONFIG = CONFIG

        self.args = args
        self.kwargs = kwargs

        self._notifier = notifier
        self._notifier.subscribe("onCountdownTakePicture", self.startCountdown)
        self._notifier.subscribe("onTakePicture", self.captureStart)
        self._notifier.subscribe(
            "onTakePictureFinished", self.captureFinished)

        self._countdownAnimationThread = StoppableThread(
            target=self._countdownAnimationFun, daemon=True)

        self._pixels = PixelStrip(CONFIG.WS2812_NUMBER_LEDS, CONFIG.WS2812_GPIO_PIN, LED_FREQ_HZ,
                                  LED_DMA, LED_INVERT, CONFIG.WS2812_MAX_BRIGHTNESS, LED_CHANNEL, LED_STRIP_TYPE)
        self._pixels.begin()
        self._fill(Color(0, 0, 0))

    def _fill(self, color=Color(0, 0, 0)):
        for i in range(self._pixels.numPixels()):
            self._pixels.setPixelColor(i, color)
        self._pixels.show()

    def _countdownAnimationFun(self):
        """Loading circle animation"""
        color = self._CONFIG.WS2812_COLOR
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

                time.sleep(self._CONFIG.WS2812_ANIMATION_UPDATE / 1000.0)

        # turn off all led when countdown ends
        self._fill(Color(0, 0, 0))

    def startCountdown(self):
        self._countdownAnimationThread = StoppableThread(
            target=self._countdownAnimationFun, daemon=True)

        self._countdownAnimationThread.start()

    def stopCountdown(self):
        if self._countdownAnimationThread.is_alive():
            self._countdownAnimationThread.stop()
            self._countdownAnimationThread.join(
                ((self._CONFIG.WS2812_ANIMATION_UPDATE+50) / 1000.0))   # wait one update run longest, afterwards continue...

        self._fill(Color(0, 0, 0))

    def captureStart(self):
        self.stopCountdown()
        self._fill(self._CONFIG.WS2812_CAPTURE_COLOR)

    def captureFinished(self):
        self.stopCountdown()
        self._fill(Color(0, 0, 0))
