from pydantic import Field
from pydantic_settings import SettingsConfigDict

from photobooth import CONFIG_PATH
from photobooth.services.config.baseconfig import BaseConfig


class WledConfig(BaseConfig):
    model_config = SettingsConfigDict(
        title="WLED Plugin Config",
        json_file=f"{CONFIG_PATH}plugin_wled.json",
        env_prefix="wled-",
    )

    wled_enabled: bool = Field(
        default=False,
        description="Enable WLED integration for user feedback during countdown and capture by LEDs.",
    )
    wled_serial_port: str = Field(
        default="",
        description="Serial port the WLED device is connected to.",
    )
