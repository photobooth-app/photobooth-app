import pluggy

hookspec = pluggy.HookspecMarker("photobooth-app")
hookimpl = pluggy.HookimplMarker("photobooth-app")


class PluginManagementSpec:
    @hookspec
    def start() -> None:
        pass

    @hookspec
    def stop() -> None:
        pass


class PluginStatemachineSpec:
    @hookspec
    def on_state_before_transition() -> None:
        pass
