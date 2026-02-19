"""
manage up to two photobooth-app backends in this module
"""

import dataclasses
import logging
import time
from functools import cache
from importlib import import_module
from io import BytesIO
from pathlib import Path
from typing import Literal

from PIL import Image, ImageDraw, ImageFont, ImageOps

from ..appconfig import appconfig
from ..plugins import pm as pluggy_pm
from .backends.abstractbackend import AbstractBackend
from .base import BaseService

logger = logging.getLogger(__name__)


class AcquisitionService(BaseService):
    def __init__(self):
        super().__init__()

        self._backends: list[AbstractBackend] = []

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

    def gen_stream(self, index_device: int = 0, index_subdevice: int = 0):
        """
        yield jpeg images to stream to client (if not created otherwise)
        this function may be overriden by backends, but this is the default one
        relies on the backends implementation of _wait_for_lores_image to return a buffer
        """
        if not appconfig.backends.enable_livestream:
            logger.warning("livestream is disabled.")
            raise ConnectionRefusedError

        while self.is_running():
            try:
                output_jpeg_bytes = self._backends[index_device].wait_for_lores_image(index_subdevice=index_subdevice)
            except StopIteration:
                return  # if backend is stopped but still requesting stream, StopIteration is sent when device is not alive any more
            except Exception as exc:
                # this error probably cannot recover.
                logger.error(f"streaming exception: {exc}")
                output_jpeg_bytes = __class__._substitute_image(
                    f":| Livestream {type(exc).__name__}",
                    f"{exc}",
                    appconfig.uisettings.livestream_mirror_effect,
                )

                self._backends[index_device].restart()

                time.sleep(0.5)  # rate limit if it fails

            yield output_jpeg_bytes

    def wait_for_still_file(self):
        """
        function blocks until high quality image is available
        """

        pluggy_pm.hook.acq_before_shot()
        pluggy_pm.hook.acq_before_get_still()

        try:
            return self._stills_backend.wait_for_still_file(appconfig.backends.retry_capture)
        except Exception as exc:
            self._stills_backend.restart()
            raise exc
        finally:
            # ensure even if failed, the wled is set to standby again
            pluggy_pm.hook.acq_after_shot()

    def wait_for_multicam_files(self):
        """
        function blocks until high quality image is available
        """

        pluggy_pm.hook.acq_before_shot()
        pluggy_pm.hook.acq_before_get_multicam()

        try:
            return self._multicam_backend.wait_for_multicam_files(appconfig.backends.retry_capture)
        except Exception as exc:
            self._multicam_backend.restart()
            raise exc
        finally:
            # ensure even if failed, the wled is set to standby again
            pluggy_pm.hook.acq_after_shot()

    def start_recording(self, video_framerate: int = 25) -> Path:
        pluggy_pm.hook.acq_before_shot()
        pluggy_pm.hook.acq_before_get_video()

        return self._video_backend.start_recording(video_framerate)

    def stop_recording(self):
        pluggy_pm.hook.acq_after_shot()

        self._video_backend.stop_recording()

    def is_recording(self):
        return self._video_backend.is_recording()

    def signalbackend_configure_optimized_for_idle(self):
        """
        set backends to idle mode (called to switched as needed by processingservice)
        called when job is finished
        """
        for backend in self._backends:
            backend._on_configure_optimized_for_idle()

    def signalbackend_configure_optimized_for_hq_preview(self):
        """
        set backends to preview mode preparing to hq capture (called to switched as needed by processingservice)
        called on start of countdown
        """
        for backend in self._backends:
            backend._on_configure_optimized_for_hq_preview()

    def signalbackend_configure_optimized_for_hq_capture(self):
        """
        set backends to hq capture mode (called to switched as needed by processingservice)
        called right before capture hq still
        """
        for backend in self._backends:
            backend._on_configure_optimized_for_hq_capture()

    def signalbackend_configure_optimized_for_video(self):
        """
        set backend to video optimized mode. currently same as for idle because idle is optimized for liveview video already.
        called on start of countdown to recording job (as preview and actual video capture are expected to work same for preview and video capture)
        """
        self.signalbackend_configure_optimized_for_idle()

    @staticmethod
    def _import_backend(backend: str):
        # dynamic import of backend

        module_path = f".backends.{backend.lower()}"
        class_name = f"{backend}Backend"
        pkg = ".".join(__name__.split(".")[:-1])  # to allow relative imports

        module = import_module(module_path, package=pkg)
        return getattr(module, class_name)

    @staticmethod
    @cache
    def _substitute_image(caption: str = "Error", message: str = "Something happened!", mirror: bool = False) -> bytes:
        """Create a substitute image in case the stream fails.
        The image shall clarify some error occured to the user while trying to recover.

        Args:
            caption (str, optional): Caption in first line. Defaults to "".
            message (str, optional): Additional error message in second line. Defaults to "".
            mirror (bool, optional): Flip left/right in case the stream has mirror effect applied. Defaults to False.

        Returns:
            bytes: _description_
        """
        path_font = Path(__file__).parent.joinpath("backends", "assets", "backend_abstract", "fonts", "Roboto-Bold.ttf").resolve()
        text_fill = "#888"
        img = Image.new("RGB", (400, 300), "#ddd")
        img_draw = ImageDraw.Draw(img)
        font_large = ImageFont.truetype(font=str(path_font), size=22)
        font_small = ImageFont.truetype(font=str(path_font), size=15)
        img_draw.text((25, 50), caption, fill=text_fill, font=font_large)
        img_draw.text((25, 80), message, fill=text_fill, font=font_small)
        img_draw.text((25, 100), "please check camera and logs", fill=text_fill, font=font_small)

        # flip if mirror effect is on because messages shall be readable on screen
        if mirror:
            img = ImageOps.mirror(img)

        # create jpeg
        jpeg_buffer = BytesIO()
        img.save(jpeg_buffer, format="jpeg", quality=95)
        return jpeg_buffer.getvalue()
