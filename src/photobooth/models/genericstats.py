from dataclasses import dataclass, field
from enum import Enum


class DisplayEnum(str, Enum):
    label = "label"
    checkbox = "checkbox"
    toggle = "toggle"
    spinner = "spinner"


@dataclass
class SubStats:
    name: str
    val: str | int | float | bool | None
    decimals: int = 0
    unit: str = ""
    display: DisplayEnum = DisplayEnum.label


@dataclass
class SubList:
    name: str
    val: list[SubStats]


@dataclass
class GenericStats:
    id: str
    name: str
    actions: list[str] = field(default_factory=list)
    stats: list[SubStats | SubList] = field(default_factory=list)
