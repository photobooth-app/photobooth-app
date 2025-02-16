"""
AppConfig class providing central config

"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from ..models.trigger import GpioTrigger, KeyboardTrigger, Trigger, UiTrigger

ParameterUiType = Literal["input", "int"]


class ShareProcessingParameters(BaseModel):
    """Configure additional parameter for the share command to input by the user."""

    model_config = ConfigDict(title="Additional parameters")

    name: str = Field(
        default="copies",
        min_length=4,
        pattern=r"^[a-zA-Z0-9]+$",
        description="Define the parameter name that is replaced in the command. Example: Set to 'copies' to replace {copies} in the command by the value.",
    )
    ui_type: ParameterUiType = Field(
        default="int",
        description="Display type of the parameter in the UI. 'int' displays ➕➖ buttons in the UI. 'input' displays an input box. This affects only the UI, all parameter are interpreted as strings.",
    )
    default: str = Field(
        default="1",
        description="Default value if the user does not change it.",
    )


class ShareProcessing(BaseModel):
    """Configure options to share or print images."""

    model_config = ConfigDict(title="Share/Print Actions")

    share_command: str = Field(
        # default="",
        description="Command issued to share/print. Use {filename} as placeholder for the mediaitem to be shared/printed.",
    )

    parameters: list[ShareProcessingParameters]

    share_blocked_time: int = Field(
        # default=10,
        description="Block queue print until time is passed. Time in seconds.",
    )

    max_shares: int = Field(
        default=0,
        ge=0,
        description="Limit max shares (0 = no limit).",
    )


class ShareConfigurationSet(BaseModel):
    """Configure stages how to process mediaitem before printing on paper."""

    model_config = ConfigDict(title="Process mediaitem before printing on paper")

    name: str = Field(
        default="default print settings",
        description="Name to identify, only used for display in admin center.",
    )

    handles_images_only: bool = Field(
        default=True,
        description="Enable if this share type can handle only still images.",
    )

    processing: ShareProcessing
    trigger: Trigger


class GroupShare(BaseModel):
    """Configure share or print actions."""

    model_config = ConfigDict(title="Define Share and Print Actions")

    sharing_enabled: bool = Field(
        default=True,
        description="Enable sharing service in general.",
    )

    number_direct_access_buttons: int = Field(
        default=1,
        ge=0,
        le=5,
        description="Number of buttons directly accessible in the gallery. Remaining items are available in the more-menu.",
    )

    actions: list[ShareConfigurationSet] = Field(
        default=[
            ShareConfigurationSet(
                handles_images_only=True,
                processing=ShareProcessing(
                    share_command="echo {filename} {copies}",
                    share_blocked_time=10,
                    parameters=[ShareProcessingParameters()],
                ),
                trigger=Trigger(
                    ui_trigger=UiTrigger(show_button=True, title="Print", icon="print"),
                    gpio_trigger=GpioTrigger(pin="23", trigger_on="pressed"),
                    keyboard_trigger=KeyboardTrigger(keycode="p"),
                ),
            ),
        ],
        description="Share or print mediaitems.",
    )
