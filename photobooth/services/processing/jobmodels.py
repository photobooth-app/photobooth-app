from enum import Enum

from ..mediacollection.mediaitem import MediaItem


class JobModel:
    """This jobmodel is controlled by the statemachine"""

    class Typ(Enum):
        undefined = 0
        image = 1
        collage = 2
        video = 3

    # job variables
    _typ: Typ = None
    _total_captures_to_take: int = None
    _last_captured_mediaitem: MediaItem = None
    _captures: list[MediaItem] = None

    # other internal variables
    countdown: float = 0

    def __init__(self):
        self._captures = []
        self._last_captured_mediaitem = None

    def __repr__(self):
        return (
            f"typ={self._typ}, total_captures_to_take={self._total_captures_to_take}, "
            f"captures={self._captures}, last_capture={self._last_captured_mediaitem}"
        )

    def validate_job(self):
        if self._typ is None or self._total_captures_to_take is None or self._captures is None:
            return False
        else:
            return True

    def reset_job(self):
        self._typ = None
        self._total_captures_to_take = None
        self._last_captured_mediaitem = None
        self._captures = None

    def add_capture(self, captured_item: MediaItem):
        self._captures.append(captured_item)

    def total_captures_to_take(self) -> int:
        assert self._total_captures_to_take is not None

        return self._total_captures_to_take

    def remaining_captures_to_take(self) -> int:
        assert self._captures is not None
        assert self._total_captures_to_take is not None

        return self._total_captures_to_take - len(self._captures)

    def number_captures_taken(self) -> int:
        assert self._captures is not None
        assert self._total_captures_to_take is not None

        return len(self._captures)

    def took_all_captures(self) -> bool:
        assert self._captures is not None
        assert self._total_captures_to_take is not None

        return len(self._captures) >= self._total_captures_to_take

    def start_model(self, typ: Typ, total_captures_to_take: int):
        self.reset_job()
        self._typ = typ
        self._total_captures_to_take = total_captures_to_take
        self._last_captured_mediaitem = None
        self._captures = []

        self.validate_job()
