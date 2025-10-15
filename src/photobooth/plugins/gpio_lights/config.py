from typing import Literal

from pydantic import BaseModel, Field
from pydantic_settings import SettingsConfigDict

from ... import CONFIG_PATH
from ...services.config.baseconfig import BaseConfig

Events = Literal["on@countdown_start", "on@start", "off@after_capture", "off@after_finished"]


class GpioLight(BaseModel):
    enable: bool = Field(
        default=True,
        description="Enable processing of this light at all.",
    )

    description: str = Field(default="main light")

    gpio_pin: int = Field(
        default=2,
        description="GPIO pin to control a light.",
    )
    active_high: bool = Field(
        default=False,
        description="Depending on your setup, choose active high (3.3V) at pin output to enable a light or active low (0V).",
    )
    events: list[Events] = Field(
        description="Switch on/off the lights when listed events occur. On app shutdown all lights are switched off.",
        default=["on@countdown_start", "off@after_capture"],
    )


class GpioLightsConfig(BaseConfig):
    model_config = SettingsConfigDict(
        title="GPIO Lights Plugin Config",
        json_file=f"{CONFIG_PATH}plugin_gpiolights.json",
        env_prefix="gpiolights-",
    )

    enabled: bool = Field(
        default=False,
        description="Enable to start the plugin at app startup",
    )

    gpio_lights: list[GpioLight] = Field(
        default=[GpioLight()],
        description="List of GPIO pins to control lights.",
    )
