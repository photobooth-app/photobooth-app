"""
AppConfig class providing central config

"""

import platform
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

backends_main_base = Literal["VirtualCamera", "WebcamCv2"]
backends_main_linux = Literal["Picamera2", "WebcamV4l", "Gphoto2"]
backends_main_win = Literal["Digicamcontrol"]
backends_main_darwin = Literal["Gphoto2"]
backends_main_concat = Literal[backends_main_base]
if platform.system() == "Linux":
    backends_main_concat = Literal[backends_main_concat, backends_main_linux]
if platform.system() == "Windows":
    backends_main_concat = Literal[backends_main_concat, backends_main_win]
if platform.system() == "Darwin":
    backends_main_concat = Literal[backends_main_concat, backends_main_darwin]

backends_live_base = Literal["Disabled", "VirtualCamera", "WebcamCv2"]
backends_live_linux = Literal["Picamera2", "WebcamV4l"]
backends_live_concat = Literal[backends_live_base]
if platform.system() == "Linux":
    backends_live_concat = Literal[backends_live_concat, backends_live_linux]
if platform.system() == "Windows":
    pass
if platform.system() == "Darwin":
    pass


class GroupBackendVirtualcamera(BaseModel):
    model_config = ConfigDict(title="VirtualCamera")
    # no additional configuration yet!

    emulate_camera_delay_still_capture: float = Field(
        default=0.2,
        multiple_of=0.1,
        ge=0,
        le=5,
        description="Emulate the delay of a camera. Time between camera is requested to deliver a still and actual delivery to the app.",
    )


class GroupBackendPicamera2(BaseModel):
    model_config = ConfigDict(title="Picamera2")

    camera_num: int = Field(
        default=0,
        description="Camera number. Usually 0 or 1.",
    )
    CAPTURE_CAM_RESOLUTION_WIDTH: int = Field(
        default=1280,
        description="camera resolution width to capture high resolution photo",
    )
    CAPTURE_CAM_RESOLUTION_HEIGHT: int = Field(
        default=720,
        description="camera resolution height to capture high resolution photo",
    )
    PREVIEW_CAM_RESOLUTION_WIDTH: int = Field(
        default=1280,
        ge=500,
        le=3500,  # hardware encoder in pi only supports max 4000 width/height
        description="camera resolution width to capture live video",
    )
    PREVIEW_CAM_RESOLUTION_HEIGHT: int = Field(
        default=720,
        ge=500,
        le=2500,  # hardware encoder in pi only supports max 4000 width/height
        description="camera resolution height to capture live video",
    )
    LIVEVIEW_RESOLUTION_WIDTH: int = Field(
        default=1280,
        ge=500,
        le=3500,  # hardware encoder in pi only supports max 4000 width/height
        description="actual resolution width for liveview stream",
    )
    LIVEVIEW_RESOLUTION_HEIGHT: int = Field(
        default=720,
        ge=500,
        le=2500,  # hardware encoder in pi only supports max 4000 width/height
        description="actual resolution height for liveview stream",
    )
    CAMERA_TRANSFORM_HFLIP: bool = Field(
        default=False,
        description="Apply horizontal flip to image source to picamera2 backend",
    )
    CAMERA_TRANSFORM_VFLIP: bool = Field(
        default=False,
        description="Apply vertical flip to image source to picamera2 backend",
    )
    optimized_lowlight_short_exposure: bool = Field(
        default=False,
        description="Raise AnalogueGain(=ISO) preferred before longer shutter times to avoid unsharp capture of moving people.",
    )
    videostream_quality: Literal["VERY_LOW", "LOW", "MEDIUM", "HIGH", "VERY_HIGH"] = Field(
        default="MEDIUM",
        description="Lower quality results in less data to be transferred and may reduce load on devices.",
    )
    original_still_quality: int = Field(
        default=90,
        ge=10,
        le=100,
        description="Picamera produces original files, this is the quality for the JPG.",
        json_schema_extra={"ui_component": "QSlider"},
    )


class GroupBackendGphoto2(BaseModel):
    model_config = ConfigDict(title="Gphoto2")

    gcapture_target: str = Field(
        default="",
        description="Set capture target (examples: 'Internal RAM', 'Memory card'). To keep images, capture to a disk target. Empty means default of camera (mostly RAM).",
    )
    disable_viewfinder_before_capture: bool = Field(
        default=True,
        description="Disable viewfinder before capture might speed up following capture autofocus. Might not work with every camera.",
    )
    iso_liveview: str = Field(
        default="",
        description="Sets the ISO for when the photobooth is in live preview modus. Very useful, when Camera does not support Exposure Simulation, and an external Flash is used. Only works when the camera is in manual. (Example Values: Auto, 100, 200, ...)",
    )
    iso_capture: str = Field(
        default="",
        description="Sets the ISO for when the photobooth captures a photo. Very useful, when Camera does not support Exposure Simulation, and an external Flash is used. Only works when the camera is in manual. (Example Values: Auto, 100, 200, ...)",
    )
    shutter_speed_liveview: str = Field(
        default="",
        description="Sets the shutter speed for the camera during the photobooth's live preview mode. Very useful, when Camera does not support Exposure Simulation, and an external Flash is used. This setting is effective only when the camera is in manual mode. (Example Values: 1, 1/5, 1/20, 1/30, 1/60, 1/1000, 1/4000, ...) Choose a very high default shutter speed in combination with Auto iso to emulate auto exposure. ",
    )
    shutter_speed_capture: str = Field(
        default="",
        description="Configures the shutter speed for the camera at the time of capturing a photo in the photobooth. Very useful, when Camera does not support Exposure Simulation, and an external Flash is used. Operational only in manual mode. (Example Values: 1/60, 1/320, 1/1000, 1/2000, 1/4000, ...)",
    )


class GroupBackendOpenCv2(BaseModel):
    model_config = ConfigDict(title="OpenCv2")

    device_index: int = Field(
        default=0,
        description="Device index of webcam. Usually 0 or 1, check docs how to determine.",
    )
    CAM_RESOLUTION_WIDTH: int = Field(
        default=10000,
        description="Resolution width requested from camera.",
    )
    CAM_RESOLUTION_HEIGHT: int = Field(
        default=10000,
        description="Resolution height requested from camera.",
    )
    CAMERA_TRANSFORM_HFLIP: bool = Field(
        default=False,
        description="Apply horizontal flip to image source to opencv2 backend",
    )
    CAMERA_TRANSFORM_VFLIP: bool = Field(
        default=False,
        description="Apply vertical flip to image source to opencv2 backend",
    )


class GroupBackendV4l2(BaseModel):
    model_config = ConfigDict(title="V4l2")

    device_index: int = Field(
        default=0,
        description="Device index of webcam. Usually 0 or 1, check docs how to determine.",
    )
    CAM_RESOLUTION_WIDTH: int = Field(
        default=10000,
        description="Resolution width requested from camera.",
    )
    CAM_RESOLUTION_HEIGHT: int = Field(
        default=10000,
        description="Resolution height requested from camera.",
    )


class GroupBackendDigicamcontrol(BaseModel):
    model_config = ConfigDict(title="Digicamcontrol")

    base_url: str = Field(
        default="http://127.0.0.1:5513",
        description="Base URL used to connect to the host running the digicamcontrol software. Usually photobooth-app and digicamcontrol are on the same computer and no adjustmend needed.",
    )


class GroupMainBackend(BaseModel):
    """
    Choose backends for still images/high quality images captured on main backend.
    If the livepreview is enabled, the video is captured from live backend (if configured)
    or main backend.
    """

    model_config = ConfigDict(title="Main Backend Configuration")

    active_backend: backends_main_concat = Field(
        title="Active Backend for stills",
        default="VirtualCamera",
        description="Main backend to use for high quality still captures. Also used for livepreview if backend is capable of.",
    )

    virtualcamera: GroupBackendVirtualcamera = GroupBackendVirtualcamera()
    webcamcv2: GroupBackendOpenCv2 = GroupBackendOpenCv2()

    if platform.system() == "Linux":
        picamera2: GroupBackendPicamera2 = GroupBackendPicamera2()
        webcamv4l: GroupBackendV4l2 = GroupBackendV4l2()
        gphoto2: GroupBackendGphoto2 = GroupBackendGphoto2()

    if platform.system() == "Windows":
        digicamcontrol: GroupBackendDigicamcontrol = GroupBackendDigicamcontrol()


class GroupLiveBackend(BaseModel):
    model_config = ConfigDict(title="Live Backend Configuration")

    active_backend: backends_live_concat = Field(
        title="Active Backend for Live-View and Video",
        default="Disabled",
        description="Secondary backend used for live streaming and video only. Useful to stream from webcam if DSLR camera has no livestream capability.",
    )

    virtualcamera: GroupBackendVirtualcamera = GroupBackendVirtualcamera()
    webcamcv2: GroupBackendOpenCv2 = GroupBackendOpenCv2()

    if platform.system() == "Linux":
        picamera2: GroupBackendPicamera2 = GroupBackendPicamera2()
        webcamv4l: GroupBackendV4l2 = GroupBackendV4l2()

    if platform.system() == "Windows":
        pass


class GroupBackends(BaseModel):
    """
    Choose backends for still images/high quality images captured on main backend.
    If the livepreview is enabled, the video is captured from live backend (if configured)
    or main backend.
    """

    model_config = ConfigDict(title="Camera Backend Config")

    enable_livestream: bool = Field(
        default=True,
        description="Enable livestream (if possible)",
    )
    livestream_framerate: int = Field(
        default=15,
        ge=5,
        le=30,
        description="Reduce the framerate to save cpu/gpu on device displaying the live preview",
    )
    retry_capture: int = Field(
        default=3,
        ge=1,
        le=5,
        description="Number of attempts to gather a picture from backend.",
    )
    countdown_camera_capture_offset: float = Field(
        default=0.2,
        multiple_of=0.05,
        ge=0,
        le=20,
        description="Trigger camera capture by offset earlier (in seconds). 0 trigger exactly when countdown is 0. Use to compensate for delay in camera processing for better UX.",
    )

    group_main: GroupMainBackend = GroupMainBackend()
    group_live: GroupLiveBackend = GroupLiveBackend()
