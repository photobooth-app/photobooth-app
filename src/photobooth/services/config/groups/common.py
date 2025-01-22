"""
AppConfig class providing central config

"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, SecretStr, SerializationInfo, field_serializer


class GroupCommon(BaseModel):
    """Common config for photobooth."""

    model_config = ConfigDict(title="Common Config")

    admin_password: SecretStr = Field(
        default=SecretStr("0000"),
        description="Password to access the admin dashboard.",
    )

    @field_serializer("admin_password")
    def contextual_serializer(self, value, info: SerializationInfo):
        if info.context:
            if info.context.get("secrets_is_allowed", False):
                return value.get_secret_value()

        return "************"

    logging_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = Field(
        default="DEBUG",
        description="Log verbosity. File is writte to disc, and latest log is displayed also in UI.",
    )

    users_delete_to_recycle_dir: bool = Field(
        default=True,
        description="If enabled, the captured files are moved to the recycle directory instead permanently deleted. Accidentally deleted images can be restored by the admin manually. Please inform users about the fact that no capture is deleted, if you enable the function!",
    )
