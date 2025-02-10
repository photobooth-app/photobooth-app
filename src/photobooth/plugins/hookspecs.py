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
    def acq_before_get_still(self) -> None:
        pass

    @hookspec
    def acq_before_get_multicam(self) -> None:
        pass

    @hookspec
    def acq_captured(self) -> None:
        pass
