class PipelineError(Exception):
    pass


class ProcessMachineOccupiedError(Exception):
    pass


class WrongMediaTypeError(Exception):
    """Used for example if videos are send to printer (which does not work even in 2025 ;)"""

    pass
