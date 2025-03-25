"""
class providing central plugin repo

"""

import importlib
import pkgutil
import sys
from enum import Enum
from importlib.metadata import entry_points

import pluggy
from PIL import Image
from statemachine import Event, State

pm = pluggy.PluginManager("photobooth-app")
hookspec = pluggy.HookspecMarker("photobooth-app")
hookimpl = pluggy.HookimplMarker("photobooth-app")


class PluginManagementSpec:
    @hookspec
    def init(self) -> None: ...

    @hookspec
    def start(self) -> None: ...

    @hookspec
    def stop(self) -> None: ...


class PluginStatemachineSpec:
    @hookspec
    def sm_before_transition(self, source: State, target: State, event: Event) -> None: ...

    @hookspec
    def sm_on_exit_state(self, source: State, target: State, event: Event) -> None: ...

    @hookspec
    def sm_on_transition(self, source: State, target: State, event: Event) -> None: ...

    @hookspec
    def sm_on_enter_state(self, source: State, target: State, event: Event) -> None: ...

    @hookspec
    def sm_after_transition(self, source: State, target: State, event: Event) -> None: ...


class PluginAcquisitionSpec:
    @hookspec  # triggers before a shot
    def acq_before_shot(self) -> None: ...

    @hookspec  # triggers before a still only
    def acq_before_get_still(self) -> None: ...

    @hookspec  # triggers before a multicam still only
    def acq_before_get_multicam(self) -> None: ...

    @hookspec  # triggers after a capture still event
    def acq_after_shot(self) -> None: ...


class PluginMediaprocessingSpec:
    @hookspec(firstresult=True)  # apply image filter
    def mp_filter_pipeline_step(self, image: Image.Image, plugin_filter: Enum, preview: bool) -> Image.Image: ...

    @hookspec  # gather all avail filter provided by plugins
    def mp_avail_filter(self) -> list[str]: ...

    @hookspec  # gather all filter to be displayed by plugins
    def mp_userselectable_filter(self) -> list[str]: ...


pm.add_hookspecs(PluginManagementSpec)
pm.add_hookspecs(PluginAcquisitionSpec)
pm.add_hookspecs(PluginStatemachineSpec)
pm.add_hookspecs(PluginMediaprocessingSpec)

# included predefined and externally installable plugins
ENTRY_POINT_GROUP = "photobooth11"  # see pyproject.toml section
entry_points_app = entry_points(group=ENTRY_POINT_GROUP)
included_plugins = [importlib.import_module(entry_point.value) for entry_point in entry_points_app]
print(f"discovered {len(included_plugins)} plugins by entry point group '{ENTRY_POINT_GROUP}':  {[plugin.__name__ for plugin in included_plugins]}")

# user plugins. additionally scan folder below working directlry for quick tinkering
sys.path.append("./plugins/")
user_plugins = [importlib.import_module(f"{name}.{name}") for _, name, ispkg in pkgutil.iter_modules(["./plugins/"]) if ispkg]
print(f"discovered {len(user_plugins)} user-plugins: {[plugin.__name__ for plugin in user_plugins]} in ./plugins/")

# register all plugins
for discovered_plugin in included_plugins + user_plugins:
    plugin_class_factory = str(discovered_plugin.__name__).split(".")[-1].title().replace("_", "")

    try:
        instance = getattr(discovered_plugin, plugin_class_factory)()  # Call the plugins object to instanciate.
    except AttributeError as exc:
        print(
            f"there is no class {plugin_class_factory} defined in {discovered_plugin.__name__}! "
            f"The plugin is broken and skipped during initialization. Error: {exc}"
        )
        continue

    pm.register(instance, name=discovered_plugin.__name__)  # Register the plugin instance
