from enum import Enum

from pydantic import Field
from pydantic_settings import SettingsConfigDict

from photobooth import CONFIG_PATH
from photobooth.services.config.baseconfig import BaseConfig

available_filter = (
    "_1977",
    "aden",
    "ashby",
    "amaro",
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
)

PilgramFilter = Enum(
    "PilgramFilter",
    ((curr, f"{curr}") for curr in available_filter),
    type=str,
)
# PilgramFilterLiteral = Literal[available_filter]


class FilterPilgram2Config(BaseConfig):
    model_config = SettingsConfigDict(title="Filter Stage Pilgram2 Plugin Config", json_file=f"{CONFIG_PATH}plugin_filter_pilgram2.json")

    add_userselectable_filter: bool = Field(
        default=True,
        description="Add userselectable filter to the list the user can choose from.",
    )
    userselectable_filter: list[PilgramFilter] = Field(
        default=[e for e in PilgramFilter],
    )
    # userselectable_filter: list[str] = Field(
    #     default=[flt for flt in available_filter],
    # )
