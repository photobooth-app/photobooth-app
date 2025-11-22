"""
AppConfig class providing central config

"""

import sys
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Orientation = Literal["1: 0°", "2: 0° mirrored", "3: 180°", "4: 180° mirrored", "5: 90°", "6: 90° mirrored", "7: 270°", "8: 270° mirrored"]


class BaseModelCamera(BaseModel):
    orientation: Orientation = Field(
        default="1: 0°",
        description="Choose the orientation of the camera. 0° is default orientation and applies no adjustment. The orientation will be set in the EXIF data so transformations are applied lossless.",
    )


class GroupCameraVirtual(BaseModelCamera):
    model_config = ConfigDict(title="VirtualCamera")
    backend_type: Literal["VirtualCamera"] = "VirtualCamera"

    framerate: int = Field(
        default=15,
        ge=5,
        le=30,
        description="Reduce the framerate to save cpu/gpu on device displaying the live preview",
    )
    emulate_hires_static_still: bool = Field(
        default=False,
        description="Deliver high-resolution still image instead the demovideo. Useful to test the processing times by emulating hires cameras.",
    )
    emulate_multicam_capture_devices: int = Field(
        default=4,
        ge=2,
        le=20,
        description="Number of emulated cameras when asking for synchronized capture for wigglegrams.",
    )


class GroupCameraPicamera2(BaseModelCamera):
    model_config = ConfigDict(title="Picamera2")
    backend_type: Literal["Picamera2"] = "Picamera2"

    camera_num: int = Field(
        default=0,
        description="Camera number. Usually 0 or 1.",
    )
    CAPTURE_CAM_RESOLUTION_WIDTH: int = Field(
        default=4608,
        description="camera resolution width to capture high resolution photo",
    )
    CAPTURE_CAM_RESOLUTION_HEIGHT: int = Field(
        default=2592,
        description="camera resolution height to capture high resolution photo",
    )
    PREVIEW_CAM_RESOLUTION_WIDTH: int = Field(
        default=2304,
        ge=500,
        le=3500,  # hardware encoder in pi only supports max 4000 width/height
        description="camera resolution width to capture live video",
    )
    PREVIEW_CAM_RESOLUTION_HEIGHT: int = Field(
        default=1296,
        ge=500,
        le=2500,  # hardware encoder in pi only supports max 4000 width/height
        description="camera resolution height to capture live video",
    )
    LIVEVIEW_RESOLUTION_WIDTH: int = Field(
        default=1152,
        ge=500,
        le=3500,  # hardware encoder in pi only supports max 4000 width/height
        description="actual resolution width for liveview stream",
    )
    LIVEVIEW_RESOLUTION_HEIGHT: int = Field(
        default=648,
        ge=500,
        le=2500,  # hardware encoder in pi only supports max 4000 width/height
        description="actual resolution height for liveview stream",
    )
    framerate_still_mode: int = Field(
        default=10,
        ge=5,
        le=30,
        description="Reduce the framerate to save cpu/gpu on device displaying the live preview",
    )
    framerate_video_mode: int = Field(
        default=25,
        ge=5,
        le=30,
        description="Reduce the framerate to save cpu/gpu on device displaying the live preview",
    )
    frame_skip_count: int = Field(
        default=2,
        ge=1,
        le=4,
        description="Reduce the framerate_video_mode by frame_skip_count to save cpu/gpu on producing device as well as client devices. Choose 1 to emit every produced frame.",
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


class GroupCameraGphoto2(BaseModelCamera):
    model_config = ConfigDict(title="Gphoto2")
    backend_type: Literal["Gphoto2"] = "Gphoto2"

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

    canon_eosmoviemode: bool = Field(
        default=False,
        description="Canon specific. Switch on/off eosmoviemode when streaming videos. Might not work with every camera.",
    )

    pause_camera_on_livestream_inactive: bool = Field(
        default=False,
        description="When enabled, the app tries to disable the cameras livestream when no livestream is requested. It helps to avoid sensor overheating for older cameras by setting viewfinder=0.",
    )
    timeout_until_inactive: int = Field(
        default=30,
        description="Delay after which the livestream is considered as inactive and camera should idle.",
    )


class GroupCameraPyav(BaseModelCamera):
    model_config = ConfigDict(title="PyAV")
    backend_type: Literal["WebcamPyav"] = "WebcamPyav"

    device_identifier: str = Field(
        default="Insta360 Link 2C",
        description="Device name (Windows) or index (Linux, Mac) of the webcam.",
        json_schema_extra={"list_api": "/api/admin/enumerate/usbcameras"},
    )

    cam_resolution_width: int = Field(
        default=3840,
        description="camera resolution width to capture high resolution photo",
    )
    cam_resolution_height: int = Field(
        default=2160,
        description="camera resolution height to capture high resolution photo",
    )
    cam_framerate: int = Field(
        default=0,
        description="Camera capture framerate. If 0, the cameras default is used. 25 or 30 are framerates likely to work.",
    )

    preview_resolution_reduce_factor: Literal[1, 2, 4, 8] = Field(
        default=2,
        description="Reduce the video and permanent livestream by this factor. Raise the factor to save CPU.",
    )
    frame_skip_count: int = Field(
        default=3,
        ge=1,
        le=8,
        description="Reduce the framerate_video_mode by frame_skip_count to save cpu/gpu on producing device as well as client devices. Choose 1 to emit every produced frame.",
    )


class GroupCameraV4l2(BaseModelCamera):
    model_config = ConfigDict(title="V4l2")
    backend_type: Literal["WebcamV4l"] = "WebcamV4l"

    device_identifier: str = Field(
        default="0",
        description="Device identifier (index 0 or 1 or /dev/xxx) of webcam.",
        json_schema_extra={"list_api": "/api/admin/enumerate/usbcameras"},
    )
    pixel_format_fourcc: Literal["MJPG", "YUYV", "YU12"] = Field(
        default="MJPG",
        description="MJPG is preferred usually. Some cameras (especially virtual cameras) do not support MJPG, so you can fall back to uncompressed YUYV here.",
    )

    CAM_RESOLUTION_WIDTH: int = Field(
        default=640,
        description="Camera resolution width in normal mode for preview and videos. Low resolution recommended to save resources.",
    )
    CAM_RESOLUTION_HEIGHT: int = Field(
        default=480,
        description="Camera resolution width in normal mode for preview and videos. Low resolution recommended to save resources.",
    )

    switch_to_high_resolution_for_stills: bool = Field(
        default=True,
        description="Enable to close camera, switch to higher resolution and grab one frame with below configuration. Resolution used for stills.",
    )
    HIRES_CAM_RESOLUTION_WIDTH: int = Field(
        default=4192,
        description="camera resolution width to capture high resolution photo",
    )
    HIRES_CAM_RESOLUTION_HEIGHT: int = Field(
        default=3104,
        description="camera resolution height to capture high resolution photo",
    )
    flush_number_frames_after_switch: int = Field(
        default=2,
        ge=0,
        le=20,
        description="After switching the format, to high resolution, the camera might need some frames to accomodate to the light again. Use the lowest numer of frames that gives the same image as before in preview mode. If too low, images might apper darker or lighter than expected.",
    )


class GroupCameraDigicamcontrol(BaseModelCamera):
    model_config = ConfigDict(title="Digicamcontrol")

    backend_type: Literal["Digicamcontrol"] = "Digicamcontrol"

    base_url: str = Field(
        default="http://127.0.0.1:5513",
        description="Base URL used to connect to the host running the digicamcontrol software. Usually photobooth-app and digicamcontrol are on the same computer and no adjustmend needed.",
    )


class WigglecamNodes(BaseModel):
    model_config = ConfigDict(title="Each camera is hooked to a node.")

    # enable: bool = Field(
    #     default=True,
    #     description="Enable node. Calibration might be invalid if chaning the nodes.",
    # )
    description: str = Field(
        default="",
        description="Description just for you to distinguish the devices.",
    )
    address: str = Field(
        default="0.0.0.0",
        description="Host or IP address to connect to the node.",
    )
    base_port: int = Field(
        default=5550,
        description="Base port to connect to the node.",
    )


class GroupCameraWigglecam(BaseModelCamera):
    model_config = ConfigDict(title="Wigglecam")

    backend_type: Literal["Wigglecam"] = "Wigglecam"

    index_cam_stills: int = Field(
        default=0,
        description="Index of one node below to capture stills.",
    )
    index_cam_video: int = Field(
        default=0,
        description="Index of one backend below to capture live preview and video.",
    )

    devices: list[WigglecamNodes] = Field(
        description="List all nodes to connect to the app. The list is considered as indexed list starting at 0. So the first node should have device_id=0. For 4 cameras you end up with 4 entries in the list and need to assign them device_id's 0,1,2,3.",
        default=[
            WigglecamNodes(description="wiggle0_device-id=0", address="wiggle0"),
            WigglecamNodes(description="wiggle1_device-id=1", address="wiggle1"),
            WigglecamNodes(description="wiggle2_device-id=2", address="wiggle2"),
            WigglecamNodes(description="wiggle3_device-id=3", address="wiggle3"),
        ],
    )


BackendsBase = GroupCameraVirtual | GroupCameraPyav | GroupCameraWigglecam
BackendsLinux = GroupCameraPicamera2 | GroupCameraV4l2 | GroupCameraGphoto2
BackendsWindows = GroupCameraDigicamcontrol
BackendsDarwin = GroupCameraGphoto2
if sys.platform == "win32":
    BackendsPlatform = BackendsBase | BackendsWindows
elif sys.platform == "linux":
    BackendsPlatform = BackendsBase | BackendsLinux
elif sys.platform == "darwin":
    BackendsPlatform = BackendsBase | BackendsDarwin
else:
    BackendsPlatform = BackendsBase


class GroupBackend(BaseModel):
    """
    Choose backends for still images/high quality images captured on main backend.
    If the livepreview is enabled, the video is captured from live backend (if configured)
    or main backend.
    """

    model_config = ConfigDict(title="Camera Configuration")

    @model_validator(mode="before")
    @classmethod
    def migrate_legacy_prev8_structure(cls, data):
        """transform non-discriminant config structure <v8 to new one. The new structure looks nicer in the frontend."""

        if "backend_config" not in data:
            print("migrating <v8 backend config structure to new model")
            data["backend_config"] = data[str(data["selected_device"]).lower()]
            data["backend_config"]["backend_type"] = data["selected_device"]  # discriminator migrate

        return data

    enabled: bool = Field(
        title="Load and start backend",
        default=True,
        description="Selected device will be loaded and started.",
    )

    description: str = Field(default="backend default name")

    backend_config: BackendsPlatform = Field(discriminator="backend_type")


class GroupCameras(BaseModel):
    """
    Choose backends for still images/high quality images captured on main backend.
    If the livepreview is enabled, the video is captured from live backend (if configured)
    or main backend.
    """

    model_config = ConfigDict(title="Camera Configurations")

    enable_livestream: bool = Field(
        default=True,
        description="Enable livestream (if possible)",
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

    index_backend_stills: int = Field(
        default=0,
        description="Index of one backend below to capture stills.",
    )
    index_backend_video: int = Field(
        default=0,
        description="Index of one backend below to capture live preview and video.",
    )
    index_backend_multicam: int = Field(
        default=0,
        description="Index of one backend below used for multicamera images (wigglegrams).",
    )

    group_backends: list[GroupBackend] = Field(
        default=[GroupBackend(description="virtual camera", backend_config=GroupCameraVirtual())],
        description="Configure the cameras here. Typical is only one camera, but it is also possible to use a DSLR for stills and another camera for the livestream.",
        title="List of Camera Backends",
    )
