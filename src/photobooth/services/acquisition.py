"""
manage up to two photobooth-app backends in this module
"""

import dataclasses
import logging
from importlib import import_module
from pathlib import Path
from typing import Literal

from ..appconfig import appconfig
from ..plugins import pm as pluggy_pm
from ..utils.exceptions import BackendNotRunning
from .backends.abstractbackend import AbstractBackend
from .backends.encoder.video import SoftwareVideoRecorder
from .base import BaseService

logger = logging.getLogger(f"{__name__}-app")


class AcquisitionService(BaseService):
    def __init__(self):
        super().__init__()

        self._backends: list[AbstractBackend] = []
        self._recorder: SoftwareVideoRecorder | None = None

    def start(self):
        super().start()

        self._backends = []

        # get backend obj and instanciate
        for cfg in appconfig.backends.group_backends:
            if cfg.enabled:
                backend: AbstractBackend = self._import_backend(cfg.backend_config.backend_type)(cfg.backend_config)

                self._backends.append(backend)
            else:
                logger.info(f"skipped starting backend {cfg} because not enabled")

        if not self._backends:
            raise RuntimeError("no backend enabled!")

        # keep a reference to the types of backends for future use:
        self._stills_backend = self._get_backend("index_backend_stills")
        self._video_backend = self._get_backend("index_backend_video")
        self._multicam_backend = self._get_backend("index_backend_multicam")

        # it's not a copy, it's a ref we hold.
        assert self._stills_backend is self._backends[appconfig.backends.index_backend_stills]

        logger.info(f"loaded backends: {[f'{index}:{name}' for index, name in enumerate(self._backends)]}")

        for backend in self._backends:
            backend.start()

        self._recorder = SoftwareVideoRecorder(self._video_backend)

        super().started()

    def stop(self):
        """stop backends"""
        super().stop()

        if not self._backends:
            return

        for backend in self._backends:
            backend.stop()

        super().stopped()

    def _get_backend(self, index_type: Literal["index_backend_stills", "index_backend_video", "index_backend_multicam"]) -> AbstractBackend:
        index = getattr(appconfig.backends, index_type)

        try:
            return self._backends[index]
        except IndexError:
            raise RuntimeError(f"illegal configuration, cannot get backend {index=} for {index_type}") from None

    def stats(self):
        """
        Gather stats from active backends.
        Backend stats are converted to dict to be processable by JSON lib

        Returns:
            _type_: _description_
        """
        acquisition_stats = {}
        for backend in self._backends:
            stats = dataclasses.asdict(backend.get_stats())
            acquisition_stats |= {str(backend): stats}

        return acquisition_stats

    def thrill_still(self):
        """called by job processor when a countdown for stills is started"""
        pluggy_pm.hook.acq_thrill()
        pluggy_pm.hook.acq_thrill_still()

    def thrill_video(self):
        """called by job processor when a countdown for video is started"""
        pluggy_pm.hook.acq_thrill()
        pluggy_pm.hook.acq_thrill_video()

    def thrill_multicam(self):
        """called by job processor when a countdown for multicam is started"""
        pluggy_pm.hook.acq_thrill()
        pluggy_pm.hook.acq_thrill_multicam()

    def wait_for_lores_image(self, index_device: int | None = 0, index_subdevice: int = 0):

        if not self.is_running():
            raise BackendNotRunning

        backend = self._video_backend if index_device is None else self._backends[index_device]

        return backend.wait_for_lores_image(index_subdevice=index_subdevice)

    def wait_for_still_file(self, index_device: int | None = 0, index_subdevice: int = 0):
        backend = self._stills_backend if index_device is None else self._backends[index_device]

        pluggy_pm.hook.acq_before_shot()
        pluggy_pm.hook.acq_before_get_still()
        try:
            return backend.wait_for_still_file(index_subdevice=index_subdevice)
        except Exception as exc:
            # self._stills_backend.recover()  # TODO: verify
            raise exc
        finally:
            # ensure even if failed, the wled is set to standby again
            pluggy_pm.hook.acq_after_shot()

    def wait_for_multicam_files(self, index_device: int | None = 0):
        backend = self._multicam_backend if index_device is None else self._backends[index_device]

        pluggy_pm.hook.acq_before_shot()
        pluggy_pm.hook.acq_before_get_multicam()

        try:
            return backend.wait_for_multicam_files()
        except Exception as exc:
            # self._multicam_backend.recover()  # TODO: verify.
            raise exc
        finally:
            # ensure even if failed, the wled is set to standby again
            pluggy_pm.hook.acq_after_shot()

    def start_recording(self, video_framerate: int = 25) -> Path:
        assert self._recorder, "service needs to be started before using the recorder"

        pluggy_pm.hook.acq_before_shot()
        pluggy_pm.hook.acq_before_get_video()

        file = self._recorder.start_recording(video_framerate)
        return file

    def stop_recording(self):
        assert self._recorder, "service needs to be started before using the recorder"

        pluggy_pm.hook.acq_after_shot()

        self._recorder.stop_recording()

    @staticmethod
    def _import_backend(backend: str):
        # dynamic import of backend

        module_path = f".backends.{backend.lower()}"
        class_name = f"{backend}Backend"
        pkg = ".".join(__name__.split(".")[:-1])  # to allow relative imports

        module = import_module(module_path, package=pkg)
        return getattr(module, class_name)
