import photobooth.services.pluginmanager as pluginmanager


@pluginmanager.hookimpl
def init(arg1, arg2):
    print("inside plugin skeleton111111111.myhook()")
    return arg1 + arg2
