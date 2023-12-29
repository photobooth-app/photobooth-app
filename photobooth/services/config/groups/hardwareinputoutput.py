"""
AppConfig class providing central config

"""


from pydantic import BaseModel, ConfigDict, Field


class GroupHardwareInputOutput(BaseModel):
    """
    Configure hardware GPIO, keyboard and more. Find integration information in the documentation.
    """

    model_config = ConfigDict(title="Hardware Input/Output Config")

    # keyboardservice config
    keyboard_input_enabled: bool = Field(
        default=False,
        description="Enable keyboard input globally",
    )
    keyboard_input_keycode_takepic: str = Field(
        default="i",
        description="Keycode triggers capture of one image",
    )
    keyboard_input_keycode_takecollage: str = Field(
        default="c",
        description="Keycode triggers capture of collage",
    )
    keyboard_input_keycode_takeanimation: str = Field(
        default="g",
        description="Keycode triggers capture of animation (GIF)",
    )
    keyboard_input_keycode_print_recent_item: str = Field(
        default="p",
        description="Keycode triggers printing most recent image captured",
    )

    # WledService Config
    wled_enabled: bool = Field(
        default=False,
        description="Enable WLED integration for user feedback during countdown and capture by LEDs.",
    )
    wled_serial_port: str = Field(
        default="",
        description="Serial port the WLED device is connected to.",
    )

    # GpioService Config
    gpio_enabled: bool = Field(
        default=False,
        description="Enable Raspberry Pi GPIOzero integration.",
    )
    gpio_pin_shutdown: int = Field(
        default=17,
        description="GPIO pin to shutdown after holding it for 2 seconds.",
    )
    gpio_pin_reboot: int = Field(
        default=18,
        description="GPIO pin to reboot after holding it for 2 seconds.",
    )
    gpio_pin_take1pic: int = Field(
        default=27,
        description="GPIO pin to take one picture.",
    )
    gpio_pin_collage: int = Field(
        default=22,
        description="GPIO pin to take a collage.",
    )
    gpio_pin_animation: int = Field(
        default=24,
        description="GPIO pin to take an animation (GIF).",
    )
    gpio_pin_print_recent_item: int = Field(
        default=23,
        description="GPIO pin to print last captured item.",
    )

    # PrintingService Config
    printing_enabled: bool = Field(
        default=False,
        description="Enable printing in general.",
    )
    printing_command: str = Field(
        default="mspaint /p {filename}",
        description="Command issued to print. Use {filename} as placeholder for the JPEG image to be printed.",
    )
    printing_blocked_time: int = Field(
        default=20,
        description="Block queue print until time is passed. Time in seconds.",
    )
