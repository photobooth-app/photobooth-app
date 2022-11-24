from pprint import *
from picamera2 import Picamera2
picam2 = Picamera2()
pprint(picam2.sensor_modes)

"""
Result for 
Arducam imx519 16mp:

[39:03:21.281347251] [732818]  INFO Camera camera.cpp:1035 configuring streams: (0) 640x480-XBGR8888 (1) 1280x720-SRGGB10_CSI2P
[39:03:21.281916489] [732819]  INFO RPI raspberrypi.cpp:765 Sensor: /base/soc/i2c0mux/i2c@1/imx519@1a - Selected sensor format: 1280x720-SRGGB10_1X10 - Selected unicam format: 1280x720-pRAA
[39:03:21.311039512] [732818]  INFO Camera camera.cpp:1035 configuring streams: (0) 640x480-XBGR8888 (1) 1920x1080-SRGGB10_CSI2P
[39:03:21.311548602] [732819]  INFO RPI raspberrypi.cpp:765 Sensor: /base/soc/i2c0mux/i2c@1/imx519@1a - Selected sensor format: 1920x1080-SRGGB10_1X10 - Selected unicam format: 1920x1080-pRAA
[39:03:21.342082599] [732818]  INFO Camera camera.cpp:1035 configuring streams: (0) 640x480-XBGR8888 (1) 2328x1748-SRGGB10_CSI2P
[39:03:21.342608910] [732819]  INFO RPI raspberrypi.cpp:765 Sensor: /base/soc/i2c0mux/i2c@1/imx519@1a - Selected sensor format: 2328x1748-SRGGB10_1X10 - Selected unicam format: 2328x1748-pRAA
[39:03:21.383276647] [732818]  INFO Camera camera.cpp:1035 configuring streams: (0) 640x480-XBGR8888 (1) 3840x2160-SRGGB10_CSI2P
[39:03:21.383703459] [732819]  INFO RPI raspberrypi.cpp:765 Sensor: /base/soc/i2c0mux/i2c@1/imx519@1a - Selected sensor format: 3840x2160-SRGGB10_1X10 - Selected unicam format: 3840x2160-pRAA
[39:03:21.422365411] [732818]  INFO Camera camera.cpp:1035 configuring streams: (0) 640x480-XBGR8888 (1) 4656x3496-SRGGB10_CSI2P
[39:03:21.422919075] [732819]  INFO RPI raspberrypi.cpp:765 Sensor: /base/soc/i2c0mux/i2c@1/imx519@1a - Selected sensor format: 4656x3496-SRGGB10_1X10 - Selected unicam format: 4656x3496-pRAA

[{'bit_depth': 10,
  'crop_limits': (1048, 1042, 2560, 1440),
  'exposure_limits': (203, 85202074),
  'format': SRGGB10_CSI2P,
  'fps': 120.0,
  'size': (1280, 720),
  'unpacked': 'SRGGB10'},
 {'bit_depth': 10,
  'crop_limits': (408, 674, 3840, 2160),
  'exposure_limits': (282, 118430097),
  'format': SRGGB10_CSI2P,
  'fps': 60.05,
  'size': (1920, 1080),
  'unpacked': 'SRGGB10'},
 {'bit_depth': 10,
  'crop_limits': (0, 0, 4656, 3496),
  'exposure_limits': (305, 127960311),
  'format': SRGGB10_CSI2P,
  'fps': 30.0,
  'size': (2328, 1748),
  'unpacked': 'SRGGB10'},
 {'bit_depth': 10,
  'crop_limits': (408, 672, 3840, 2160),
  'exposure_limits': (491, 206049113),
  'format': SRGGB10_CSI2P,
  'fps': 18.0,
  'size': (3840, 2160),
  'unpacked': 'SRGGB10'},
 {'bit_depth': 10,
  'crop_limits': (0, 0, 4656, 3496),
  'exposure_limits': (592, 248567756),
  'format': SRGGB10_CSI2P,
  'fps': 9.0,
  'size': (4656, 3496),
  'unpacked': 'SRGGB10'}]


pi@photobooth:~ $ libcamera-hello --list-cameras
Available cameras
-----------------
0 : imx519 [4656x3496] (/base/soc/i2c0mux/i2c@1/imx519@1a)
    Modes: 'SRGGB10_CSI2P' : 1280x720 [120.00 fps - (1048, 1042)/2560x1440 crop]
                             1920x1080 [60.05 fps - (408, 674)/3840x2160 crop]
                             2328x1748 [30.00 fps - (0, 0)/4656x3496 crop]
                             3840x2160 [18.00 fps - (408, 672)/3840x2160 crop]
                             4656x3496 [9.00 fps - (0, 0)/4656x3496 crop]


"""
