"""
AppConfig class providing central config

"""

from pydantic import BaseModel, ConfigDict, Field


class GroupHardwareInputOutput(BaseModel):
    """
    Configure hardware GPIO, keyboard and more. Find integration information in the documentation.
    """

    model_config = ConfigDict(title="Hardware Input/Output Config")

    # keyboard config
    keyboard_input_enabled: bool = Field(
        default=False,
        description="Enable keyboard input globally. Keyup is catched in browsers connected to the app.",
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

    gpio_pin_job_next: int = Field(
        default=27,
        description="If a job is active, this pin is used to confirm/continue the job process if manual input is required for example to approve.",
    )
    gpio_pin_job_reject: int = Field(
        default=22,
        description="If a job is active, this pin is used to reject a capture during approval.",
    )
    gpio_pin_job_abort: int = Field(
        default=20,
        description="If a job is active, this pin is used to abort the job.",
    )
