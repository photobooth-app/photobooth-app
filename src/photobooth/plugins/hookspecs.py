import pluggy

hookspec = pluggy.HookspecMarker("photobooth-app")


@hookspec
def init(arg1, arg2) -> None:
    pass


@hookspec
def start() -> None:
    pass


@hookspec
def stop() -> None:
    pass


@hookspec
def on_state_before_transition() -> None:
    pass
