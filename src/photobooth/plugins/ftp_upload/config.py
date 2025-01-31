from pydantic import ConfigDict, Field

from photobooth.services.config.appconfig_ import BaseConfig


class FtpPluginConfig(BaseConfig):
    model_config = ConfigDict(title="Ftp Plugin Config")

    test_: str = Field(
        default="teststr",
        description="test description.",
    )


print("CONFIG LOADED")
