"""
class providing central plugin repo

"""

import pluggy

PLUGGY_PROJECT_NAME = "photobooth-app"

pm = pluggy.PluginManager(PLUGGY_PROJECT_NAME)

hookspec = pluggy.HookspecMarker(PLUGGY_PROJECT_NAME)
hookimpl = pluggy.HookimplMarker(PLUGGY_PROJECT_NAME)
