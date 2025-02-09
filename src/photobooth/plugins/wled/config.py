from pydantic import Field
from pydantic_settings import SettingsConfigDict

from photobooth import CONFIG_PATH
from photobooth.services.config.baseconfig import BaseConfig


class WledConfig(BaseConfig):
    model_config = SettingsConfigDict(title="WLED Plugin Config", json_file=f"{CONFIG_PATH}plugin_wled.json")

    plugin_enabled: bool = Field(
        default=False,
        description="Enable to start the plugin with app startup",
    )
