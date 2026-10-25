from dataclasses import dataclass, field
from pathlib import Path
from uuid import UUID, uuid4


@dataclass
class UiCaptureDefinition:
    name: str
    width: int
    height: int


@dataclass
class UiFrameOverlay:
    image: Path
    mirror_effect: bool


@dataclass
class UiJobModel:
    typ: str
    total_captures_to_take: int
    remaining_captures_to_take: int
    number_captures_taken: int
    duration: float
    present_mediaitem_id: str | None
    approval_id: str | None
    captures_definition: UiCaptureDefinition | None
    frame_overlay: UiFrameOverlay | None
    is_long_running_filter: bool = False
    latest_capture_id: str | None = None


@dataclass
class Capture:
    filepath: Path
    uuid: UUID = field(default_factory=uuid4)

    target_width: int | None = None  # currently used to allow approval screen to crop correctly as it would be in final collage
    target_height: int | None = None

    def __repr__(self):
        return f"<{self.__class__.__name__}> file {self.filepath}"


@dataclass
class CaptureSet:
    captures: list[Capture]
    uuid: UUID = field(default_factory=uuid4)
