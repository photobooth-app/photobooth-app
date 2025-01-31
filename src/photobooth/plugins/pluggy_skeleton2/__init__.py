import photobooth.services.pluginmanager as pluginmanager


@pluginmanager.hookimpl
def init(arg1, arg2):
    print("inside plugin skeleton2!!!!!!!!!.myhook()")
    return arg1 - arg2
