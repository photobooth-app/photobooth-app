from statemachine import Event, State

from . import hookspec


class PluginManagementSpec:
    @hookspec
    def start(self) -> None: ...  #

    @hookspec
    def stop(self) -> None: ...  #


class PluginStatemachineSpec:
    @hookspec
    def sm_before_transition(self, source: State, target: State, event: Event) -> None: ...  #

    @hookspec
    def sm_on_exit_state(self, source: State, target: State, event: Event) -> None: ...  #

    @hookspec
    def sm_on_transition(self, source: State, target: State, event: Event) -> None: ...  #

    @hookspec
    def sm_on_enter_state(self, source: State, target: State, event: Event) -> None: ...  #

    @hookspec
    def sm_after_transition(self, source: State, target: State, event: Event) -> None: ...  #


class PluginAcquisitionSpec:
    @hookspec
    def acq_before_shot(self) -> None: ...  # triggers before a shot

    @hookspec
    def acq_before_get_still(self) -> None: ...  # triggers before a still only

    @hookspec
    def acq_before_get_multicam(self) -> None: ...  # triggers before a multicam still only

    @hookspec
    def acq_after_shot(self) -> None: ...  # triggers after a capture still event
