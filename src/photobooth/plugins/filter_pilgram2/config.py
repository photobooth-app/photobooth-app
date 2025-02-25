from typing import Literal, get_args

from pydantic import Field
from pydantic_settings import SettingsConfigDict

from photobooth import CONFIG_PATH
from photobooth.services.config.baseconfig import BaseConfig

available_filter = Literal[
    "_1977",
    "aden",
    "amaro",
    "ashby",
    "brannan",
    "brooklyn",
    "charmes",
    "clarendon",
    "crema",
    "dogpatch",
    "earlybird",
    "gingham",
    "ginza",
    "hefe",
    "helena",
    "hudson",
    "inkwell",
    "juno",
    "kelvin",
    "lark",
    "lofi",
    "ludwig",
    "maven",
    "mayfair",
    "moon",
    "nashville",
    "perpetua",
    "poprocket",
    "reyes",
    "rise",
    "sierra",
    "skyline",
    "slumber",
    "stinson",
    "sutro",
    "toaster",
    "valencia",
    "walden",
    "willow",
    "xpro2",
]


class FilterPilgram2Config(BaseConfig):
    model_config = SettingsConfigDict(title="Filter Stage Pilgram2 Plugin Config", json_file=f"{CONFIG_PATH}plugin_filter_pilgram2.json")

    add_userselectable_filter: bool = Field(
        default=True,
        description="Add userselectable filter to the list the user can choose from.",
    )
    userselectable_filter: list[available_filter] = Field(
        default=[f for f in get_args(available_filter)],
        description="Select filter, the user can choose from. Even if unselected here, the filter is still available in the admin configuration.",
    )
