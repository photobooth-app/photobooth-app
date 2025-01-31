from .config import FtpPluginConfig


class FtpPlugin:
    def __init__(self):
        self._config: FtpPluginConfig = FtpPluginConfig()

        print("__PLUGIN INIT")

        print(self._config.test_)

        # self._config.persist()

    def start(self):
        pass

    def stop(self):
        pass

    def upload(self, file):
        pass
