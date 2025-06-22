from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import SettingsConfigDict

from photobooth import CONFIG_PATH
from photobooth.services.config.baseconfig import BaseConfig


class GpioLightsConfig(BaseConfig):
    model_config = SettingsConfigDict(title="GPIO Lights Plugin Config", json_file=f"{CONFIG_PATH}plugin_gpiolights.json")

    plugin_enabled: bool = Field(
        default=False,
        description="Enable to start the plugin with app startup",
    )

    gpio_pin_light_list: list[int] = Field(
        default_factory=lambda: [
            2,
        ],
        description="List of GPIO pins to control lights. The first pin is mandatory, the others are optional. ",
        validation_alias=AliasChoices("gpio_pin_light_list", "gpio_pin_light"),
    )

    # Ensures that the old format single pin attribute is converted to a list
    @field_validator("gpio_pin_light_list", mode="before")
    @classmethod
    def convert_single_pin_to_list(cls, value):
        if isinstance(value, int):
            return [value]
        return value

    active_high: bool = Field(
        default=False,
        description="Set to True if the GPIO pin is active high, False if it is active low.",
    )
    gpio_light_off_after_capture: bool = Field(
        default=True,
        description="Turn the light off after every capture.",
    )
