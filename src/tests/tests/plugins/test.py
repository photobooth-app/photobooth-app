from unittest.mock import MagicMock, patch

import pluggy

hookspec = pluggy.HookspecMarker("example")
hookimpl = pluggy.HookimplMarker("example")


class HookSpec:
    @hookspec
    def my_hook(self, arg):
        """A hook specification"""


pm = pluggy.PluginManager("example")
pm.add_hookspecs(HookSpec)


class MyPlugin:
    @hookimpl
    def my_hook(self, arg):
        print(f"Original hook called with {arg}")  # Debugging output


plugin = MyPlugin()
pm.register(plugin)  # Register BEFORE mocking

# ✅ Get the function reference that Pluggy actually calls
hookimpls = pm.hook.my_hook.get_hookimpls()
print(hookimpls)
assert hookimpls, "Pluggy did not register the hook properly!"
actual_hook_function = hookimpls[0].function  # The stored function reference

# ✅ Patch the exact function Pluggy calls
with patch.object(hookimpls[0], "function", new=MagicMock()) as mock_hook:
    pm.hook.my_hook(arg="test")  # Call hook

    # ✅ Now the assertion should pass!
    mock_hook.assert_called_once_with("test")
