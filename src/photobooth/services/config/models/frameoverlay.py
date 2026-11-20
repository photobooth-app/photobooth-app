from pydantic import BaseModel, Field

from .models import FilePathOrNone


class FrameOverlay(BaseModel):
    enable: bool = Field(
        default=False,
        description="Enable to overlay to be displayed.",
    )
    image: FilePathOrNone = Field(
        # factories are not part of json schema export. path is not json convertible so it would warn and not include the default. using factory, we skip the warning for same outcome.
        default=None,
        description="This image frame is overlayed the camera images. This image determines the output image size and aspect ratio during image processing. Photos are visible through transparant parts, so the overlay should be in PNG format usually.",
        json_schema_extra={"list_api": "/api/admin/enumerate/userfiles"},
    )
    mirror_effect: bool = Field(
        default=False,
        description="Flip the overlay image horizontally. This can be when the livestream is also flipped (mirror-effect on) as it helps users to gather and align in the scene. Text in the overlay appears in the wrong direction but the final image is correct as the effect is only applied during display, not job processing.",
    )
