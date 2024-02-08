"""
AppConfig class providing central config for ui

These settings are 1:1 sent to the vue frontend.
Remember to keep the settings in sync! Fields added here need to be added to the frontend also.

"""


from pydantic import BaseModel, ConfigDict, Field

from .mediaprocessing import EnumPilgramFilter


class GroupUiSettings(BaseModel):
    """Personalize the booth's UI."""

    model_config = ConfigDict(title="Personalize the User Interface")

    PRIMARY_COLOR: str = Field(
        default="#196cb0",
        description="Primary color (e.g. buttons, title bar).",
        json_schema_extra={"ui_component": "ColorPicker"},
    )

    SECONDARY_COLOR: str = Field(
        default="#b8124f",
        description="Secondary color (admin interface, accents).",
        json_schema_extra={"ui_component": "ColorPicker"},
    )

    show_takepic_on_frontpage: bool = Field(
        default=True,
        description="Show button to capture single picture on frontpage.",
    )
    show_takecollage_on_frontpage: bool = Field(
        default=True,
        description="Show button to capture collage on frontpage.",
    )
    show_takeanimation_on_frontpage: bool = Field(
        default=True,
        description="Show button to capture animated GIF on frontpage.",
    )
    show_takevideo_on_frontpage: bool = Field(
        default=True,
        description="Show button to capture video on frontpage.",
    )
    show_gallery_on_frontpage: bool = Field(
        default=True,
        description="Show button to gallery on frontpage.",
    )
    show_admin_on_frontpage: bool = Field(
        default=True,
        description="Show button to admin center, usually only during setup.",
    )

    livestream_mirror_effect: bool = Field(
        default=True,
        description="Flip livestream horizontally to create a mirror effect feeling more natural to users.",
    )
    FRONTPAGE_TEXT: str = Field(
        default='<div class="fixed-center text-h2 text-weight-bold text-center text-white" style="text-shadow: 4px 4px 4px #666;">Hey!<br>Let\'s take some pictures! <br>📷💕</div>',
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
    gallery_show_filter: bool = Field(
        default=True,
        description="Show instagramlike filter (pilgram2).",
    )
    gallery_filter_userselectable: list[EnumPilgramFilter] = Field(
        title="Pic1 Filter Userselectable",
        default=[e.value for e in EnumPilgramFilter],
        description="Filter the user may choose from in the gallery. 'original' applies no filter.",
    )
    gallery_show_download: bool = Field(
        default=True,
        description="Show download button in gallery.",
    )
    gallery_show_delete: bool = Field(
        default=True,
        description="Show delete button for items in gallery.",
    )
    gallery_show_print: bool = Field(
        default=True,
        description="Show print button for items in gallery.",
    )
