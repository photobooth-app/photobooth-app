"""
AppConfig class providing central config

"""

from pydantic import BaseModel, ConfigDict, Field


class GroupSharing(BaseModel):
    """Settings about shareing media"""

    model_config = ConfigDict(title="🫶 Share Config")

    shareservice_enabled: bool = Field(
        default=False,
        description="Enable share service. To enable URL needs to be configured and dl.php script setup properly.",
    )
    shareservice_url: str = Field(
        default="https://photobooth-app.org/extras/shareservice-landing/",
        description="URL of php script that is used to serve files and share via QR code. The default is a landingpage with further instructions how to setup.",
    )
    shareservice_apikey: str = Field(
        default="changedefault!",
        description="Key to secure the download php script. Set the key in dl.php script to same value. Only if correct key is provided the shareservice works properly.",
    )
    shareservice_share_original: bool = Field(
        default=False,
        description="Upload original image as received from camera. If unchecked, the full processed version is uploaded with filter and texts applied.",
    )

    share_custom_qr_url: str = Field(
        default="http://localhost/media/processed/full/{filename}",
        description="URL displayed as QR code to image for download. Need you to sync the files on your own or allow the user to access via hotspot. {filename} is replaced by actual filename in QR code.",
    )
