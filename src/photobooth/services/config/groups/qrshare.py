"""
AppConfig class providing central config

"""

from platform import node

from pydantic import BaseModel, ConfigDict, Field

hostname = node() if node() != "" else "localhost"


class GroupQrShare(BaseModel):
    """Settings about shareing media"""

    model_config = ConfigDict(title="QR code share")

    enabled: bool = Field(
        default=False,
        description="(DEPRECATED in v8) Enable qr share service. To enable URL needs to be configured and dl.php script setup properly.",
        # json_schema_extra={"deprecated": "v8"},
    )
    shareservice_url: str = Field(
        default="https://photobooth-app.org/extras/shareservice-landing/",
        description="(DEPRECATED in v8) URL of php script that is used to serve files and share via QR code. The default is a landingpage with further instructions how to setup.",
        # json_schema_extra={"deprecated": "v8"},
    )
    shareservice_apikey: str = Field(
        default="changedefault!",
        description="(DEPRECATED in v8) Key to secure the download php script. Set the key in dl.php script to same value. Only if correct key is provided the shareservice works properly.",
        # json_schema_extra={"deprecated": "v8"},
    )

    enabled_custom: bool = Field(
        default=False,
        description="Enable qr share service. To enable URL needs to be configured and dl.php script setup properly.",
    )
    share_custom_qr_url: str = Field(
        default=f"http://{hostname}:8000/download/#?url=http://{hostname}:8000/media/full/{{identifier}}",
        description="URL displayed as QR code to image for download. Need you to sync the files on your own or allow the user to access via hotspot. {identifier} is replaced by the actual item's id, {filename} is replaced by the actual filename on the photobooth-data, in QR code.",
    )
