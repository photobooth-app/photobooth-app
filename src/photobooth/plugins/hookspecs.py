from statemachine import Event, State

from . import hookspec


class PluginManagementSpec:
    @hookspec
    def start(self) -> None:
        pass

    @hookspec
    def stop(self) -> None:
        pass


class PluginStatemachineSpec:
    @hookspec
    def sm_before_transition(self, source: State, target: State, event: Event) -> None:
        pass

    @hookspec
    def sm_on_exit_state(self, source: State, target: State, event: Event) -> None:
        pass

    @hookspec
    def sm_on_transition(self, source: State, target: State, event: Event) -> None:
        pass

    @hookspec
    def sm_on_enter_state(self, source: State, target: State, event: Event) -> None:
        pass

    @hookspec
    def sm_after_transition(self, source: State, target: State, event: Event) -> None:
        pass


class PluginAcquisitionSpec:
    @hookspec
    def acq_capture_before_trigger(self) -> None:
        pass

    def acq_capture_after_trigger(self) -> None:
        pass

    def acq_capture_captured(self) -> None:
        pass
