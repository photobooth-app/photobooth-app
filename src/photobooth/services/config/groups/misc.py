"""
AppConfig class providing central config

"""

from pydantic import BaseModel, ConfigDict, Field


class GroupMisc(BaseModel):
    """
    Quite advanced or experimental, usually not necessary to touch. Can change any time.
    """

    model_config = ConfigDict(title="Miscellaneous Config")

    secret_key: str = Field(
        default="ThisIsTheDefaultSecret",
        min_length=8,
        max_length=64,
        description="Secret to encrypt authentication data. If changed, login authorization is invalidated.",
    )

    cmd_shutdown: str = Field(
        default="shutdown now",
        description="Command to shutdown when requested by the app. Change it if you have custom UPS solutions that need to poweroff properly.",
    )

    cmd_reboot: str = Field(
        default="reboot",
        description="Command to reboot when requested by the app. Change it if you have custom UPS solutions that need to poweroff properly.",
    )
