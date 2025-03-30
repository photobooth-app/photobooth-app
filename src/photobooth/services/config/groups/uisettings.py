from pathlib import Path
from typing import Annotated, Literal

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, FilePath
from pydantic_extra_types.color import Color

from ..validators import ensure_demoassets


class GroupUiSettings(BaseModel):
    """Personalize the booth's UI."""

    model_config = ConfigDict(title="Personalize the User Interface")

    PRIMARY_COLOR: Color = Field(
        default=Color("#196cb0"),
        description="Primary color (e.g. buttons, title bar).",
    )

    SECONDARY_COLOR: Color = Field(
        default=Color("#b8124f"),
        description="Secondary color (admin interface, accents).",
    )

    theme: Literal["system", "light", "dark"] = Field(
        default="system",
        description="Specify the theme for the app. Set to system for automatic switching based on system/browser settings or force the light/dark theme.",
    )

    show_gallery_on_frontpage: bool = Field(
        default=True,
        description="Show button to gallery on frontpage.",
    )
    show_admin_on_frontpage: bool = Field(
        default=True,
        description="Show button to admin center, usually only during setup.",
    )
    admin_button_invisible: bool = Field(
        default=False,
        description="If button is shown, it can still be rendered invisible. If enabled, the button is 100% transparent and 5 clicks each within 500ms are required to access the admin login.",
    )

    show_frontpage_timeout: int = Field(
        default=5,
        ge=1,
        description="Idle timeout in minutes after which the app switches to the frontpage again.",
    )
    enable_automatic_slideshow: bool = Field(
        default=True,
        description="Enable a random slideshow after some time without any user interaction.",
    )
    show_automatic_slideshow_timeout: int = Field(
        default=300,
        ge=30,
        description="Timeout in seconds after which the slideshow starts.",
    )

    enable_livestream_when_idle: bool = Field(
        default=True,
        description="When idle, the cameras livestream is displayed permanently.",
    )
    enable_livestream_when_active: bool = Field(
        default=True,
        description="When countdown or capture is active, the cameras livestream is displayed.",
    )
    livestream_mirror_effect: bool = Field(
        default=True,
        description="Flip livestream horizontally to create a mirror effect feeling more natural to users.",
    )
    livestream_blurredbackground: bool = Field(
        default=False,
        description="Display the livestream blurred in the background of the actual livestream covering the full screen. This might look nice if the livestream resolution does not match the screen's aspect ratio. Check cpu usage on low power devices.",
    )
    enable_livestream_frameoverlay: bool = Field(
        default=True,
        description="Enable to overlay livestream_frameoverlay_image the livestream.",
    )
    livestream_frameoverlay_image: Annotated[FilePath | None, BeforeValidator(ensure_demoassets)] = Field(
        default=Path("userdata/demoassets/frames/frame_image_photobooth-app.png"),
        description="When enabled, the frame is overlayed the livestream. This image is not used in the postprocessing. If mirroreffect is on, it will also be mirrored. Text in the frame appears in the wrong direction but the final image is correct.",
        json_schema_extra={"files_list_api": "/api/admin/files/search"},
    )
    livestream_frameoverlay_mirror_effect: bool = Field(
        default=False,
        description="Flip the frame overlaid horizontally to create a mirror effect. Useful to flip also if video is flipped when people shall align to the frame. If there is text in the frame it's also mirrored.",
    )

    FRONTPAGE_TEXT: str = Field(
        default='<div class="fixed-center text-h2 text-weight-bold text-center text-white" style="text-shadow: 4px 4px 4px #666;">Hey!<br>Let\'s take some pictures! <br>📷</div>',
        description="Text/HTML displayed on frontpage.",
    )

    TAKEPIC_MSG_TIME: float = Field(
        default=0.5,
        description="Offset in seconds, the smile-icon shall be shown.",
    )
    TAKEPIC_MSG_TEXT: str = Field(
        default="😃",
        description="Message to display at the end of the capture countdown.",
    )

    AUTOCLOSE_NEW_ITEM_ARRIVED: int = Field(
        default=30,
        description="Timeout in seconds a new item popup closes automatically.",
    )

    GALLERY_EMPTY_MSG: str = Field(
        default='<div class="fixed-center text-h2 text-weight-bold text-center text-white" style="text-shadow: 4px 4px 4px #666;">Empty, Zero, Nada! 🤷‍♂️<br>Let\'s take some pictures! <br>📷💕</div>',
        description="Message displayed if gallery is empty.",
    )
    gallery_show_qrcode: bool = Field(
        default=True,
        description="Show QR code in gallery. If shareservice is enabled the URL is automatically generated, if not go to share config and provide URL.",
    )
    qrcode_text_above: str = Field(
        default="👋 Download your photo!",
        description="Display text above the QR code.",
    )
    qrcode_text_below: str = Field(
        default="Scan above code with your phone.",
        description="Display text below the QR code.",
    )
    gallery_show_filter: bool = Field(
        default=True,
        description="Show filter provided by plugins. Pilgram2 filter are included in the app. See documentation to extend and build your own plugin.",
    )
    gallery_show_download: bool = Field(
        default=True,
        description="Show a download button in gallery.",
    )
    gallery_show_delete: bool = Field(
        default=True,
        description="Show a delete button in gallery.",
    )
    gallery_show_shareprint: bool = Field(
        default=True,
        description="Show the share/print buttons in gallery.",
    )
