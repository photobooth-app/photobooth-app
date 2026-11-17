from dataclasses import dataclass, field


@dataclass
class StillRetry:
    """Returned by a plugin from the acq_still_check hook to request one more still capture.

    parameters: camera settings (name -> value) that are applied for the retry only,
    on top of the configured still parameterset. Supported by backends that expose
    named camera parameters (currently gphoto2); other backends ignore it.
    reason: free text for the log.
    """

    parameters: dict[str, str] = field(default_factory=dict)
    reason: str = ""
