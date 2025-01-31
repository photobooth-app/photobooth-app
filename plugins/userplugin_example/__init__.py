import photobooth.services.pluginmanager as pluginmanager


@pluginmanager.hookimpl
def init(arg1, arg2):
    print("DYN LOADED USER PLUGIN myhook() MULTIPLIES 💗")
    return arg1 * arg2
