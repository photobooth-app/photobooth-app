"""
AppConfig class providing central config

"""

from pydantic import BaseModel, ConfigDict, Field


class GroupFileTransfer(BaseModel):
    """Configuration for USB File Transfer Service."""

    model_config = ConfigDict(title="USB File Transfer Service Config")

    enabled: bool = Field(
        default=False,
        description="Enable the automatic file transfer to USB service. Files are copied when the USB drive is inserted.",
    )
    target_folder_name: str = Field(
        default="photobooth",
        description="Name of the top-level folder on the USB drive where files will be copied to.",
    )
