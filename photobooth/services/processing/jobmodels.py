import time
from enum import Enum
from threading import Condition, Thread

from ..mediacollection.mediaitem import MediaItem


class CountdownTimer:
    TIMER_TICK = 0.1
    TIMER_TOLERANCE = 0.05  # to account for float not 100% accurate
    TIMER_MAX_DURATION = 20

    def __init__(self):
        self._duration: float = 0
        self._countdown: float = 0
        self._remaining_record_time: float = 0

        self._ticker_thread: Thread = None
        self._finished_condition: Condition = Condition()

    def start(self, duration: float):
        self._duration = duration
        self._countdown = duration

        self._ticker_thread = Thread(name="_ticker_thread", target=self._ticker_fun, daemon=True)
        self._ticker_thread.start()

    def reset(self):
        self._duration = 0
        self._countdown = 0
        self._remaining_record_time = 0

    def wait_countdown_finished(self, timeout: float = (TIMER_MAX_DURATION + 1)):
        # TODO: timeout needs to be higher than max possible value to avoid any deadlocks

        # return early if already finished when called.
        # to avoid any race condition if countdown from 0 but wait_countdown was not called yet so condition is missed.
        if self._countdown_finished():
            return

        with self._finished_condition:
            if not self._finished_condition.wait(timeout=timeout):
                raise TimeoutError("error timing out")

    def _countdown_finished(self):
        return self._countdown <= self.TIMER_TOLERANCE

    def _ticker_fun(self):
        while not self._countdown_finished():
            time.sleep(0.1)

            self._countdown -= self.TIMER_TICK

        # ticker finished, reset
        self.reset()

        # notify waiting threads
        with self._finished_condition:
            self._finished_condition.notify_all()

        # done, exit fun, exit thread


class JobModel:  # TODO: derive from model class?
    """This jobmodel is controlled by the statemachine"""

    class Typ(str, Enum):
        undefined = "undefined"
        image = "image"
        collage = "collage"
        animation = "animation"
        video = "video"

    def __init__(self):
        """_summary_
        Init model

        """
        # job description
        self._typ: __class__.Typ = None

        # job model processing vars
        self._confirmed_captures_collection: list[MediaItem] = []
        self._total_captures_to_take: int = 0
        self._last_captured_mediaitem: MediaItem = None

        # job metadata processing ui interaction
        self._collage_automatic_capture_continue = False

        # job model timer
        self._duration_user: float = 0
        self._countdown_timer: CountdownTimer = CountdownTimer()

    def export(self) -> dict:
        """Export model as dict for UI (needds to be jsonserializable)

        following variables + the "self.state" variable (added by state machine automagically) will be exported.
        __class__.export() is used to json-serialize and send to frontend the current model state whenever need to update.

        Returns:
            dict: _description_
        """
        out = dict(
            state=self.state,
            typ=self._typ,
            total_captures_to_take=self.total_captures_to_take(),
            remaining_captures_to_take=self.remaining_captures_to_take(),
            number_captures_taken=self.number_captures_taken(),
            duration=self._duration_user,
            ask_user_for_approval=self.ask_user_for_approval(),
            confirmed_captures_collection=[captured_item.asdict() for captured_item in self._confirmed_captures_collection]
            if self._confirmed_captures_collection
            else [],
            last_captured_mediaitem=self._last_captured_mediaitem.asdict() if self._last_captured_mediaitem else None,
        )

        return out

    def __repr__(self):
        return (
            f"typ={self._typ}, total_captures_to_take={self._total_captures_to_take}, "
            f"confirmed_captures_collection={self._confirmed_captures_collection}, last_capture={self._last_captured_mediaitem}"
        )

    def _validate_job(self):
        if (
            self._typ is None
            or self._total_captures_to_take is None
            or self._total_captures_to_take < 1
            or self._confirmed_captures_collection is None
        ):
            return False
        else:
            return True

    # external model processing controls
    def add_confirmed_capture_to_collection(self, captured_item: MediaItem):
        self._confirmed_captures_collection.append(captured_item)  # most recent is always at N pos., get latest with get_last_capture

    def last_capture_successful(self) -> bool:
        return self._last_captured_mediaitem is not None

    def set_last_capture(self, last_mediaitem: MediaItem):
        self._last_captured_mediaitem = last_mediaitem

    def get_last_capture(self) -> MediaItem:
        return self._last_captured_mediaitem

    def total_captures_to_take(self) -> int:
        assert self._total_captures_to_take is not None

        return self._total_captures_to_take

    def remaining_captures_to_take(self) -> int:
        assert self._confirmed_captures_collection is not None
        assert self._total_captures_to_take is not None

        return self._total_captures_to_take - len(self._confirmed_captures_collection)

    def number_captures_taken(self) -> int:
        assert self._confirmed_captures_collection is not None
        assert self._total_captures_to_take is not None

        return len(self._confirmed_captures_collection)

    def all_captures_confirmed(self) -> bool:
        assert self._confirmed_captures_collection is not None
        assert self._total_captures_to_take is not None

        return len(self._confirmed_captures_collection) >= self._total_captures_to_take

    def ask_user_for_approval(self) -> bool:
        # display only for collage (multistep process if configured, otherwise always false)
        if self._typ is JobModel.Typ.collage and not self._collage_automatic_capture_continue:
            return True
        else:
            return False

    def jobtype_recording(self) -> bool:
        # to check if mode is video or HQ captures request
        if self._typ is JobModel.Typ.video:
            return True
        else:
            return False

    # external model start/stop controls
    def start_model(self, typ: Typ, total_captures_to_take: int, collage_automatic_capture_continue: bool = False):
        self.reset_job()
        self._typ = typ
        self._total_captures_to_take = total_captures_to_take
        self._last_captured_mediaitem = None
        self._confirmed_captures_collection = []
        self._collage_automatic_capture_continue = collage_automatic_capture_continue

        self._validate_job()

    def reset_job(self):
        self._typ = None
        self._total_captures_to_take = 0
        self._last_captured_mediaitem = None
        self._confirmed_captures_collection = []

    # external countdown controls
    def start_countdown(self, duration_user: float, offset_camera: float = 0.0):
        """Countdown until camera shall trigger

        duration_user: Total time displayed to frontend user
        duration_capture: Time until camera is triggered to start capture

        Args:
            duration (float): _description_
        """

        # countdown is capped to maximum
        self._duration_user = duration_user if duration_user < CountdownTimer.TIMER_MAX_DURATION else CountdownTimer.TIMER_MAX_DURATION
        _offset_camera = offset_camera if (offset_camera <= duration_user) else duration_user

        self._countdown_timer.start(duration=(duration_user - _offset_camera))

    def wait_countdown_finished(self):
        self._countdown_timer.wait_countdown_finished()
        self._duration_user = 0
