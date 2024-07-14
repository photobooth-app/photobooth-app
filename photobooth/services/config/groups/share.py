"""
AppConfig class providing central config

"""

from pydantic import BaseModel, ConfigDict, Field

from ..models.trigger import GpioTrigger, KeyboardTrigger, Trigger, UiTrigger


class ShareProcessing(BaseModel):
    """Configure options to share or print images."""

    model_config = ConfigDict(title="Share/Print Actions")

    share_command: str = Field(
        # default="",
        description="Command issued to share/print. Use {filename} as placeholder for the mediaitem to be shared/printed.",
    )
    share_blocked_time: int = Field(
        # default=10,
        description="Block queue print until time is passed. Time in seconds.",
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
                    share_command="mspaint /p {filename}",
                    share_blocked_time=10,
                ),
                trigger=Trigger(
                    ui_trigger=UiTrigger(show_button=True, title="Print", icon="o_print"),
                    gpio_trigger=GpioTrigger(pin="23", trigger_on="pressed"),
                    keyboard_trigger=KeyboardTrigger(keycode="p"),
                ),
            ),
        ],
        description="Share or print mediaitems.",
    )
