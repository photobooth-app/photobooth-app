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

    key: str = Field(
        default="copies",
        min_length=4,
        pattern=r"^[a-zA-Z0-9]+$",
        description="Define the parameter key that is replaced in the command. Example: Set to 'copies' to replace {copies} in the command by the value.",
    )
    label: str = Field(
        default="Copies",
        description="Label the field, displayed to the user.",
    )
    ui_type: ParameterUiType = Field(
        default="int",
        description="Display type of the parameter in the UI. 'int' displays ➕➖ buttons in the UI. 'input' displays an input box. This affects only the UI, all parameter are interpreted as strings.",
    )
    default: str = Field(
        default="1",
        description="Default value if the user does not change it.",
    )
    valid_min: str = Field(default="1")
    valid_max: str = Field(default="3")


class ShareProcessing(BaseModel):
    """Configure options to share or print images."""

    model_config = ConfigDict(title="Share/Print Actions")

    share_command: str = Field(
        default="echo {filename}",
        description="Command issued to share/print. Use {filename} as placeholder for the mediaitem to be shared/printed.",
    )
    ask_user_for_parameter_input: bool = Field(
        default=False,
        description="If enabled, when the share button is activated, a dialog pops up to input below configured parameters.",
    )
    parameters_dialog_caption: str = Field(
        default="Make your choice!",
        description="Caption of the dialog popup displaying the parameters.",
    )
    parameters_dialog_action_icon: str = Field(
        default="print",
        description="Icon used for the action button (any icon from material icons, see documentation).",
    )
    parameters_dialog_action_label: str = Field(
        default="GO",
        description="Text used for the action button as label.",
    )

    parameters: list[ShareProcessingParameters] = Field(
        default=[],
        description="Define input fields the user needs to enter on share.",
    )

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
                handles_images_only=False,
                processing=ShareProcessing(
                    share_command="echo {filename} {copies}",
                    ask_user_for_parameter_input=False,
                    parameters_dialog_caption="How many copies?",
                    share_blocked_time=3,
                    parameters=[ShareProcessingParameters()],
                ),
                trigger=Trigger(
                    ui_trigger=UiTrigger(show_button=True, title="Print", icon="print"),
                    gpio_trigger=GpioTrigger(pin="23", trigger_on="pressed"),
                    keyboard_trigger=KeyboardTrigger(keycode="p"),
                ),
            ),
            ShareConfigurationSet(
                handles_images_only=True,
                processing=ShareProcessing(
                    share_command="echo {filename} {copies} {mail}",
                    ask_user_for_parameter_input=True,
                    parameters_dialog_caption="Print and mail...",
                    parameters_dialog_action_icon="mail",
                    parameters_dialog_action_label="send",
                    share_blocked_time=3,
                    parameters=[
                        ShareProcessingParameters(),
                        ShareProcessingParameters(
                            key="mail",
                            label="E-Mail address",
                            ui_type="input",
                            default="me@mgineer85.de",
                            valid_min="5",
                            valid_max="128",
                        ),
                    ],
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
