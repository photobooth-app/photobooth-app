from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class UiTrigger(BaseModel):
    """
    UI trigger configuration.
    """

    model_config = ConfigDict(title="UI button configuration")

    show_button: bool = Field(
        default=True,
        description="Show the button to trigger the process.",
    )
    title: str = Field(
        default="",
        description="Label used for the button.",
    )
    icon: str = Field(
        default="",
        description="Icon used for the button (any icon from material icons, see documentation).",
    )


class KeyboardTrigger(BaseModel):
    """
    Configure trigger the user can interact with. Sources are GPIO and keyboard.
    """

    model_config = ConfigDict(title="Keyboard triggers configuration")

    keycode: str = Field(
        default="",
        description="Define keyboard keys to trigger actions.",
    )


class GpioTrigger(BaseModel):
    """
    Configure trigger the user can interact with. Sources are GPIO and keyboard.
    """

    model_config = ConfigDict(title="GPIO triggers configuration")

    pin: str = Field(
        default="",
        description="GPIO the button is connected to.",
    )

    trigger_on: Literal["pressed", "released", "longpress"] = Field(
        default="pressed",
        description="Trigger action when button pressed (contact closed), released (contact open after closed) or longpress (hold for 0.6 seconds).",
    )


class Trigger(BaseModel):
    """
    Configure trigger the user can interact with. Sources are GPIO and keyboard.
    """

    model_config = ConfigDict(title="Trigger configuration")

    ui_trigger: UiTrigger = UiTrigger()
    keyboard_trigger: KeyboardTrigger = KeyboardTrigger()
    gpio_trigger: GpioTrigger = GpioTrigger()
