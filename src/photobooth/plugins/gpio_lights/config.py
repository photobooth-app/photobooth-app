from pydantic import Field
from pydantic_settings import SettingsConfigDict

from photobooth import CONFIG_PATH
from photobooth.services.config.baseconfig import BaseConfig


class GpioLightsConfig(BaseConfig):
    model_config = SettingsConfigDict(title="GPIO Lights Plugin Config", json_file=f"{CONFIG_PATH}plugin_gpiolights.json")

    plugin_enabled: bool = Field(
        default=False,
        description="Enable to start the plugin with app startup",
    )

    gpio_pin_light: int = Field(
        default=2,
        description="First GPIO pin to control a light.",
    )
    active_high: bool = Field(
        default=False,
        description="Set to True if the GPIO pin is active high, False if it is active low.",
    )
    gpio_pin_light2: int | None = Field(
        default=None,
        description="Second GPIO pin to control a light (leave empty if not used).",
    )
    gpio_pin_light3: int | None = Field(
        default=13,
        description="Third GPIO pin to control a light (leave empty if not used).",
    )
    gpio_light_off_after_capture: bool = Field(
        default=True,
        description="Turn the light off after every capture.",
    )
