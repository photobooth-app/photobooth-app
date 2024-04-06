"""
AppConfig class providing central config

"""

import platform
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class BackendsMain(str, Enum):
    "Main backend to use for high quality still captures. Also used for livepreview if backend is capable of."

    VIRTUALCAMERA = "VirtualCamera"

    WEBCAMCV2 = "WebcamCv2"

    if platform.system() == "Linux":
        PICAMERA2 = "Picamera2"
        WEBCAMV4L = "WebcamV4l"
        GPHOTO2 = "Gphoto2"

    if platform.system() == "Windows":
        DIGICAMCONTROL = "Digicamcontrol"


class BackendsLive(str, Enum):
    "Secondary backend used for live streaming only. Useful to stream from webcam if DSLR camera has no livestream capability."

    DISABLED = "Disabled"

    VIRTUALCAMERA = "VirtualCamera"
    WEBCAMCV2 = "WebcamCv2"

    if platform.system() == "Linux":
        PICAMERA2 = "Picamera2"
        WEBCAMV4L = "WebcamV4l"

    if platform.system() == "Windows":
        pass


class GroupBackends(BaseModel):
    """
    Choose backends for still images/high quality images captured on main backend.
    If the livepreview is enabled, the video is captured from live backend (if configured)
    or main backend.
    """

    model_config = ConfigDict(title="Camera Backend Config")

    MAIN_BACKEND: BackendsMain = Field(
        title="Main Backend",
        default=BackendsMain.VIRTUALCAMERA,
        description="Main backend to use for high quality still captures. Also used for livepreview if backend is capable of.",
    )
    LIVE_BACKEND: BackendsLive = Field(
        title="Live Backend",
        default=BackendsLive.DISABLED,
        description="Secondary backend used for live streaming only. Useful to stream from webcam if DSLR camera has no livestream capability.",
    )
    LIVEPREVIEW_ENABLED: bool = Field(
        default=True,
        description="Enable livestream (if possible)",
    )
    LIVEPREVIEW_FRAMERATE: int = Field(
        default=15,
        ge=5,
        le=30,
        description="Reduce the framerate to save cpu/gpu on device displaying the live preview",
        json_schema_extra={"ui_component": "QSlider"},
    )
    retry_capture: int = Field(
        default=3,
        ge=1,
        le=5,
        description="Number of attempts to gather a picture from backend.",
    )

    gphoto2_capture_target: str = Field(
        default="",
        description="Set capture target (examples: 'Internal RAM', 'Memory card'). To keep images, capture to a disk target. Empty means default of camera (mostly RAM).",
    )
    gphoto2_disable_viewfinder_before_capture: bool = Field(
        default=True,
        description="Disable viewfinder before capture might speed up following capture autofocus. Might not work with every camera.",
    )
    gphoto2_iso_liveview: str = Field(
        default="",
        description="Sets the ISO for when the photobooth is in live preview modus. Very useful, when Camera does not support Exposure Simulation, and an external Flash is used. Only works when the camera is in manual. (Example Values: Auto, 100, 200, ...)",
    )
    gphoto2_iso_capture: str = Field(
        default="",
        description="Sets the ISO for when the photobooth captures a photo. Very useful, when Camera does not support Exposure Simulation, and an external Flash is used. Only works when the camera is in manual. (Example Values: Auto, 100, 200, ...)",
    )
    gphoto2_shutter_speed_liveview: str = Field(
        default="",
        description="Sets the shutter speed for the camera during the photobooth's live preview mode. Very useful, when Camera does not support Exposure Simulation, and an external Flash is used. This setting is effective only when the camera is in manual mode. (Example Values: 1, 1/5, 1/20, 1/30, 1/60, 1/1000, 1/4000, ...) Choose a very high default shutter speed in combination with Auto iso to emulate auto exposure. ",
    )
    gphoto2_shutter_speed_capture: str = Field(
        default="",
        description="Configures the shutter speed for the camera at the time of capturing a photo in the photobooth. Very useful, when Camera does not support Exposure Simulation, and an external Flash is used. Operational only in manual mode. (Example Values: 1/60, 1/320, 1/1000, 1/2000, 1/4000, ...)",
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

    digicamcontrol_base_url: str = Field(
        default="http://127.0.0.1:5513",
        description="Base URL used to connect to the host running the digicamcontrol software. Usually photobooth-app and digicamcontrol are on the same computer and no adjustmend needed.",
    )

    picamera2_CAPTURE_CAM_RESOLUTION_WIDTH: int = Field(
        default=1280,
        description="camera resolution width to capture high resolution photo",
    )
    picamera2_CAPTURE_CAM_RESOLUTION_HEIGHT: int = Field(
        default=720,
        description="camera resolution height to capture high resolution photo",
    )
    picamera2_PREVIEW_CAM_RESOLUTION_WIDTH: int = Field(
        default=1280,
        ge=500,
        le=3500,  # hardware encoder in pi only supports max 4000 width/height
        description="camera resolution width to capture live video",
    )
    picamera2_PREVIEW_CAM_RESOLUTION_HEIGHT: int = Field(
        default=720,
        ge=500,
        le=2500,  # hardware encoder in pi only supports max 4000 width/height
        description="camera resolution height to capture live video",
    )
    picamera2_LIVEVIEW_RESOLUTION_WIDTH: int = Field(
        default=1280,
        ge=500,
        le=3500,  # hardware encoder in pi only supports max 4000 width/height
        description="actual resolution width for liveview stream",
    )
    picamera2_LIVEVIEW_RESOLUTION_HEIGHT: int = Field(
        default=720,
        ge=500,
        le=2500,  # hardware encoder in pi only supports max 4000 width/height
        description="actual resolution height for liveview stream",
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
    picamera2_stream_quality: Literal["VERY_LOW", "LOW", "MEDIUM", "HIGH", "VERY_HIGH"] = Field(
        title="Picamera2 Stream Quality (for livepreview)",
        default="MEDIUM",
        description="Lower quality results in less data to be transferred and may reduce load on display device.",
    )
