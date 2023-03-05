# pylint: skip-file

from pprint import *
from picamera2 import Picamera2

picam2 = Picamera2()
pprint(picam2.sensor_modes)

"""

Result for 
Raspberry Pi Camera Module 3 (imx708):

[0:07:17.296134597] [1656]  INFO Camera camera_manager.cpp:299 libcamera v0.0.2+55-5df5b72c
[0:07:17.456542125] [1659]  INFO RPI raspberrypi.cpp:1425 Registered camera /base/soc/i2c0mux/i2c@1/imx708@1a to Unicam device /dev/media3 and ISP device /dev/media0
[0:07:17.470058500] [1656]  INFO Camera camera.cpp:1026 configuring streams: (0) 640x480-XBGR8888 (1) 1536x864-SBGGR10_CSI2P
[0:07:17.470762514] [1659]  INFO RPI raspberrypi.cpp:805 Sensor: /base/soc/i2c0mux/i2c@1/imx708@1a - Selected sensor format: 1536x864-SBGGR10_1X10 - Selected unicam format: 1536x864-pBAA
[0:07:17.508738135] [1656]  INFO Camera camera.cpp:1026 configuring streams: (0) 640x480-XBGR8888 (1) 2304x1296-SBGGR10_CSI2P
[0:07:17.509996839] [1659]  INFO RPI raspberrypi.cpp:805 Sensor: /base/soc/i2c0mux/i2c@1/imx708@1a - Selected sensor format: 2304x1296-SBGGR10_1X10 - Selected unicam format: 2304x1296-pBAA
[0:07:17.563098739] [1656]  INFO Camera camera.cpp:1026 configuring streams: (0) 640x480-XBGR8888 (1) 4608x2592-SBGGR10_CSI2P
[0:07:17.563771034] [1659]  INFO RPI raspberrypi.cpp:805 Sensor: /base/soc/i2c0mux/i2c@1/imx708@1a - Selected sensor format: 4608x2592-SBGGR10_1X10 - Selected unicam format: 4608x2592-pBAA
[{'bit_depth': 10,
  'crop_limits': (0, 0, 4608, 2592),
  'exposure_limits': (9, 603302, None),
  'format': SRGGB10_CSI2P,
  'fps': 120.13,
  'size': (1536, 864),
  'unpacked': 'SRGGB10'},
 {'bit_depth': 10,
  'crop_limits': (0, 0, 4608, 2592),
  'exposure_limits': (13, 875283, None),
  'format': SRGGB10_CSI2P,
  'fps': 56.03,
  'size': (2304, 1296),
  'unpacked': 'SRGGB10'},
 {'bit_depth': 10,
  'crop_limits': (0, 0, 4608, 2592),
  'exposure_limits': (26, 1722331, None),
  'format': SRGGB10_CSI2P,
  'fps': 14.35,
  'size': (4608, 2592),
  'unpacked': 'SRGGB10'}]

pi@photobooth:~ $ libcamera-hello --list-cameras
0 : imx708 [4608x2592] (/base/soc/i2c0mux/i2c@1/imx708@1a)
    Modes: 'SRGGB10_CSI2P' : 1536x864 [120.13 fps - (0, 0)/4608x2592 crop]
                             2304x1296 [56.03 fps - (0, 0)/4608x2592 crop]
                             4608x2592 [14.35 fps - (0, 0)/4608x2592 crop]





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


"""
Result for 
Arducam 64mp Hawkeye:

[0:29:59.022302744] [2696]  INFO RPI raspberrypi.cpp:1404 Registered camera /base/soc/i2c0mux/i2c@1/arducam_64mp@1a to Unicam device /dev/media3 and ISP device /dev/media2
[0:29:59.062776816] [2695]  INFO Camera camera.cpp:1035 configuring streams: (0) 640x480-XBGR8888 (1) 1280x720-SBGGR10_CSI2P
[0:29:59.063721570] [2696]  INFO RPI raspberrypi.cpp:765 Sensor: /base/soc/i2c0mux/i2c@1/arducam_64mp@1a - Selected sensor format: 1280x720-SBGGR10_1X10 - Selected unicam format: 1280x720-pBAA
[0:29:59.102142277] [2695]  INFO Camera camera.cpp:1035 configuring streams: (0) 640x480-XBGR8888 (1) 1920x1080-SBGGR10_CSI2P
[0:29:59.103122605] [2696]  INFO RPI raspberrypi.cpp:765 Sensor: /base/soc/i2c0mux/i2c@1/arducam_64mp@1a - Selected sensor format: 1920x1080-SBGGR10_1X10 - Selected unicam format: 1920x1080-pBAA
[0:29:59.155436029] [2695]  INFO Camera camera.cpp:1035 configuring streams: (0) 640x480-XBGR8888 (1) 2312x1736-SBGGR10_CSI2P
[0:29:59.156404586] [2696]  INFO RPI raspberrypi.cpp:765 Sensor: /base/soc/i2c0mux/i2c@1/arducam_64mp@1a - Selected sensor format: 2312x1736-SBGGR10_1X10 - Selected unicam format: 2312x1736-pBAA
[0:29:59.202887294] [2695]  INFO Camera camera.cpp:1035 configuring streams: (0) 640x480-XBGR8888 (1) 3840x2160-SBGGR10_CSI2P
[0:29:59.204116740] [2696]  INFO RPI raspberrypi.cpp:765 Sensor: /base/soc/i2c0mux/i2c@1/arducam_64mp@1a - Selected sensor format: 3840x2160-SBGGR10_1X10 - Selected unicam format: 3840x2160-pBAA
[0:29:59.309471985] [2695]  INFO Camera camera.cpp:1035 configuring streams: (0) 640x480-XBGR8888 (1) 4624x3472-SBGGR10_CSI2P
[0:29:59.310402729] [2696]  INFO RPI raspberrypi.cpp:765 Sensor: /base/soc/i2c0mux/i2c@1/arducam_64mp@1a - Selected sensor format: 4624x3472-SBGGR10_1X10 - Selected unicam format: 4624x3472-pBAA
[0:29:59.466212516] [2695]  INFO Camera camera.cpp:1035 configuring streams: (0) 640x480-XBGR8888 (1) 9152x6944-SBGGR10_CSI2P
[0:29:59.469048185] [2696]  INFO RPI raspberrypi.cpp:765 Sensor: /base/soc/i2c0mux/i2c@1/arducam_64mp@1a - Selected sensor format: 9152x6944-SBGGR10_1X10 - Selected unicam format: 9152x6944-pBAA



[{'bit_depth': 10,
  'crop_limits': (2064, 2032, 5120, 2880),
  'exposure_limits': (76, 71022430),
  'format': SRGGB10_CSI2P,
  'fps': 120.03,
  'size': (1280, 720),
  'unpacked': 'SRGGB10'},
 {'bit_depth': 10,
  'crop_limits': (784, 1312, 7680, 4320),
  'exposure_limits': (107, 99944031),
  'format': SRGGB10_CSI2P,
  'fps': 60.04,
  'size': (1920, 1080),
  'unpacked': 'SRGGB10'},
 {'bit_depth': 10,
  'crop_limits': (0, 0, 9248, 6944),
  'exposure_limits': (131, 122583595),
  'format': SRGGB10_CSI2P,
  'fps': 30.0,
  'size': (2312, 1736),
  'unpacked': 'SRGGB10'},
 {'bit_depth': 10,
  'crop_limits': (784, 1312, 7680, 4320),
  'exposure_limits': (201, 187817977),
  'format': SRGGB10_CSI2P,
  'fps': 20.0,
  'size': (3840, 2160),
  'unpacked': 'SRGGB10'},
 {'bit_depth': 10,
  'crop_limits': (0, 0, 9248, 6944),
  'exposure_limits': (254, 237626884),
  'format': SRGGB10_CSI2P,
  'fps': 10.0,
  'size': (4624, 3472),
  'unpacked': 'SRGGB10'},
 {'bit_depth': 10,
  'crop_limits': (0, 0, 9152, 6944),
  'exposure_limits': (467, 435921136),
  'format': SRGGB10_CSI2P,
  'fps': 2.7,
  'size': (9152, 6944),
  'unpacked': 'SRGGB10'}]



0 : arducam_64mp [9248x6944] (/base/soc/i2c0mux/i2c@1/arducam_64mp@1a)
    Modes: 'SRGGB10_CSI2P' : 1280x720 [120.03 fps - (2064, 2032)/5120x2880 crop]
                             1920x1080 [60.04 fps - (784, 1312)/7680x4320 crop]
                             2312x1736 [30.00 fps - (0, 0)/9248x6944 crop]
                             3840x2160 [20.00 fps - (784, 1312)/7680x4320 crop]
                             4624x3472 [10.00 fps - (0, 0)/9248x6944 crop]
                             9152x6944 [2.70 fps - (0, 0)/9152x6944 crop]


"""
