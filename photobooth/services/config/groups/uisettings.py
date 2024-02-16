"""
AppConfig class providing central config for ui

These settings are 1:1 sent to the vue frontend.
Remember to keep the settings in sync! Fields added here need to be added to the frontend also.

"""
import json
from pathlib import Path
from typing import Any

from pydantic import Field
from pydantic.fields import FieldInfo
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource, SettingsConfigDict

from .mediaprocessing import EnumPilgramFilter

SETTING_FIELDNAME = "uisettings"
CONFIG_FILENAME = "./config/config.json"  # can't import from appsettings during initilization


class JsonConfigSubSettingsSource(PydanticBaseSettingsSource):
    """
    A simple settings source class that loads variables from a JSON file
    at the project's root.

    Here we happen to choose to use the `env_file_encoding` from Config
    when reading `config.json`
    """

    def get_field_value(self, field: FieldInfo, field_name: str) -> tuple[Any, str, bool]:
        encoding = self.config.get("env_file_encoding")
        field_value = None
        try:
            file_content_json = json.loads(Path(CONFIG_FILENAME).read_text(encoding))
            subSetting_json = file_content_json.get(SETTING_FIELDNAME)
            field_value = subSetting_json.get(field_name)
        except FileNotFoundError:
            # ignore file not found, because it could have been deleted or not yet initialized
            # using defaults
            pass

        return field_value, field_name, False

    def prepare_field_value(self, field_name: str, field: FieldInfo, value: Any, value_is_complex: bool) -> Any:
        return value

    def __call__(self) -> dict[str, Any]:
        d: dict[str, Any] = {}

        for field_name, field in self.settings_cls.model_fields.items():
            field_value, field_key, value_is_complex = self.get_field_value(field, field_name)
            field_value = self.prepare_field_value(field_name, field, field_value, value_is_complex)
            if field_value is not None:
                d[field_key] = field_value

        return d


class GroupUiSettings(BaseSettings):
    """Personalize the booth's UI."""

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
    number_of_collage_configurations: int = Field(
        default=1,
        ge=1,
        description="How many collage configurations to show on frontpage.",
    )
    number_of_animation_configurations: int = Field(
        default=1,
        ge=1,
        description="How many GIF configuration to show on frontpage.",
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

    model_config = SettingsConfigDict(
        env_file_encoding="utf-8",
        # first in following list is least important; last .env file overwrites the other.
        env_file=[".env.installer", ".env.dev", ".env.test", ".env.prod"],
        env_nested_delimiter="__",
        case_sensitive=True,
        extra="ignore",
        title="User Interface",
    )

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        """customize sources"""
        return (
            init_settings,
            JsonConfigSubSettingsSource(settings_cls),
            dotenv_settings,
            env_settings,
            file_secret_settings,
        )
