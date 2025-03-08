import typing

from pydantic import Field
from pydantic_settings import SettingsConfigDict

from photobooth import CONFIG_PATH
from photobooth.services.config.baseconfig import BaseConfig

available_filter = typing.Literal[
    "anime",
    "astronaut",
    "caricature",
    "clay",
    "comic",
    "gotcha",
    "impasto",
    "kids",
    "marble",
    "medieval",
    "neotokyo",
    "pencil",
    "retro",
    "scifi",
    "vaporwave",
    "watercolor"
]

class FilterStablediffusionConfig(BaseConfig):
    model_config = SettingsConfigDict(title="Stablediffusion Filter Plugin Config", json_file=f"{CONFIG_PATH}plugin_filter_stable.json")

    add_userselectable_filter: bool = Field(
        default=True,
        description="Add userselectable filter to the list the user can choose from.",
    )
    userselectable_filter: list[available_filter] = Field(
        default=[f for f in typing.get_args(available_filter)],
        description="Select filter, the user can choose from. Even if unselected here, the filter is still available in the admin configuration.",
    )
