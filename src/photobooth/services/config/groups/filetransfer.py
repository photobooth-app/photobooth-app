"""
AppConfig class providing central config

"""

from pydantic import BaseModel, ConfigDict, Field


class GroupFileTransfer(BaseModel):
    """Configuration for USB File Transfer Service."""

    model_config = ConfigDict(title="USB File Transfer Service Config (deprecated since v8)")

    enabled: bool = Field(
        default=False,
        description="(DEPRECATED in v8) Enable the automatic file transfer to USB service. Files are copied when the USB drive is inserted.",
        # json_schema_extra={"deprecated": "v8"},
    )
    target_folder_name: str = Field(
        default="photobooth",
        description="(DEPRECATED in v8) Name of the top-level folder on the USB drive where files will be copied to.",
        # json_schema_extra={"deprecated": "v8"},
    )
