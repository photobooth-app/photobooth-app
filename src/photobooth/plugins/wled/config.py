from pydantic import BaseModel, Field
from pydantic_settings import SettingsConfigDict

from ... import CONFIG_PATH
from ...services.config.baseconfig import BaseConfig


class Common(BaseModel):
    enabled: bool = Field(
        default=False,
        description="Enable WLED integration for user feedback during countdown and capture by LEDs.",
    )
    serial_port: str = Field(
        default="",
        description="Serial port the WLED device is connected to.",
        json_schema_extra={"list_api": "/api/admin/enumerate/serialports"},
    )

    use_separate_thrill_presets: bool = Field(
        default=False,
        description="Enable to distinguish the countdown preset for stills/video/multicamera jobs. This is useful if you have multiple cameras and show an animation directed to the lens of the camera. You need to add the presets 20, 21 and 22 to the WLED module. See documentation for more details and reference presets for download.",
    )


class WledConfig(BaseConfig):
    model_config = SettingsConfigDict(
        title="WLED Plugin Config",
        json_file=f"{CONFIG_PATH}plugin_wled.json",
        env_prefix="wled-",
    )

    common: Common = Common()
