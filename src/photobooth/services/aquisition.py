"""
manage up to two photobooth-app backends in this module
"""

import dataclasses
import logging
import subprocess
import time
from functools import cache
from importlib import import_module
from io import BytesIO
from pathlib import Path
from threading import current_thread
from typing import cast

from PIL import Image, ImageDraw, ImageFont, ImageOps

from ..appconfig import appconfig
from ..plugins import pm as pluggy_pm
from ..utils.stoppablethread import StoppableThread
from .backends.abstractbackend import AbstractBackend
from .base import BaseService

logger = logging.getLogger(__name__)


class AquisitionService(BaseService):
    def __init__(self):
        super().__init__()

        self._backends: list[AbstractBackend] = []
        self._supervisor_thread: StoppableThread | None = None

    def start(self):
        super().start()

        self._backends = []

        # get backend obj and instanciate
        for backend_config in appconfig.backends.group_backends:
            if backend_config.enabled:
                backend: AbstractBackend = self._import_backend(backend_config.selected_device)(
                    getattr(backend_config, str(backend_config.selected_device).lower())
                )

                self._backends.append(backend)
            else:
                logger.info(f"skipped starting backend {backend_config} because not enabled")

        if not self._backends:
            raise RuntimeError("no backend enabled!")

        # validate during startup that all indexes are in valid range. TODO: move to pydantic config logic at any point?
        max_index = max(appconfig.backends.index_backend_stills, appconfig.backends.index_backend_video, appconfig.backends.index_backend_multicam)
        if max_index > len(self._backends) - 1:
            raise RuntimeError(f"configuration error: index out of range! {max_index=} whereas max_index allowed={len(self._backends) - 1}")

        logger.info(f"loaded backends: {self._backends}")

        self._load_ffmpeg()

        self._supervisor_thread = StoppableThread(name="_supervisor_thread", target=self._supervisor_fun, args=(), daemon=True)
        self._supervisor_thread.start()

        super().started()

    def stop(self):
        """stop backends"""
        super().stop()

        if self._supervisor_thread and self._supervisor_thread.is_alive():
            self._supervisor_thread.stop()
            self._supervisor_thread.join()

        super().stopped()

    def _device_start(self):
        logger.info("starting device")

        try:
            for backend in self._backends:
                backend.start()
        except Exception as exc:
            logger.exception(exc)
            logger.critical("could not init/start backend")

            self.faulty()

            return

        logger.info("device started")

    def _device_stop(self):
        if not self._backends:
            return

        for backend in self._backends:
            backend.stop()

    def _device_alive(self):
        backends_are_alive = all([backend._device_alive() for backend in self._backends])
        return backends_are_alive and True

    def _supervisor_fun(self):
        logger.info("device supervisor started, checking for clock, then starting device")
        flag_stopped_orphaned_already = False

        while not cast(StoppableThread, current_thread()).stopped():
            if not self._device_alive() or any([backend.is_marked_faulty.is_set() for backend in self._backends]):
                logger.info("starting devices...")
                if not flag_stopped_orphaned_already:
                    # to ensure after device was not alive (means just 1 thread stopped), we stop all threads
                    self._device_stop()
                    flag_stopped_orphaned_already = True

                flag_stopped_orphaned_already = False

                try:
                    self._device_start()
                except Exception as exc:
                    logger.exception(exc)
                    logger.error(f"error starting device: {exc}")

                    self._device_stop()

            # wait up to 3 seconds but in smaller increments so if service is stopped,
            # break out of the sleep loop. since .stopped is true, the outer while is also left.
            for _ in range(30):
                time.sleep(0.1)
                if cast(StoppableThread, current_thread()).stopped():
                    break

        logger.info("device supervisor exit, stopping devices")
        self._device_stop()  # safety first, maybe it's double stopped, but prevent any stalling of device-threads

        logger.info("left _supervisor_fun")

    def stats(self):
        """
        Gather stats from active backends.
        Backend stats are converted to dict to be processable by JSON lib

        Returns:
            _type_: _description_
        """
        aquisition_stats = {}
        for backend in self._backends:
            stats = dataclasses.asdict(backend.get_stats())
            aquisition_stats |= {str(backend): stats}

        return aquisition_stats

    def _get_stills_backend(self) -> AbstractBackend:
        index = appconfig.backends.index_backend_stills
        try:
            return self._backends[index]
        except IndexError as exc:
            raise ValueError(f"illegal configuration, cannot get backend {index=}") from exc

    def _get_video_backend(self) -> AbstractBackend:
        index = appconfig.backends.index_backend_video
        try:
            return self._backends[index]
        except IndexError as exc:
            raise ValueError(f"illegal configuration, cannot get backend {index=}") from exc

    def _get_multicam_backend(self) -> AbstractBackend:
        index = appconfig.backends.index_backend_multicam
        try:
            return self._backends[index]
        except IndexError as exc:
            raise ValueError(f"illegal configuration, cannot get backend {index=}") from exc

    def gen_stream(self):
        """
        assigns a backend to generate a stream
        """

        if appconfig.backends.enable_livestream:
            return self._get_stream_from_backend(self._get_video_backend())

        raise ConnectionRefusedError("livepreview not enabled")

    def wait_for_still_file(self):
        """
        function blocks until high quality image is available
        """

        pluggy_pm.hook.acq_before_shot()
        pluggy_pm.hook.acq_before_get_still()

        try:
            still_backend = self._get_stills_backend()
            return still_backend.wait_for_still_file(appconfig.backends.retry_capture)
        except Exception as exc:
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
            multicam_backend = self._get_multicam_backend()
            return multicam_backend.wait_for_multicam_files(appconfig.backends.retry_capture)
        except Exception as exc:
            raise exc
        finally:
            # ensure even if failed, the wled is set to standby again
            pluggy_pm.hook.acq_after_shot()

    def start_recording(self, video_framerate: int = 25):
        self._get_video_backend().start_recording(video_framerate)

    def stop_recording(self):
        self._get_video_backend().stop_recording()

    def is_recording(self):
        return self._get_video_backend().is_recording()

    def get_recorded_video(self):
        return self._get_video_backend().get_recorded_video()

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

    def _get_stream_from_backend(self, backend_to_stream_from: AbstractBackend):
        """
        yield jpeg images to stream to client (if not created otherwise)
        this function may be overriden by backends, but this is the default one
        relies on the backends implementation of _wait_for_lores_image to return a buffer
        """
        logger.info(f"livestream started on backend {backend_to_stream_from=}")

        while self.is_running():
            try:
                output_jpeg_bytes = backend_to_stream_from.wait_for_lores_image()
            except StopIteration:
                return  # if backend is stopped but still requesting stream, StopIteration is sent when device is not alive any more
            except Exception as exc:
                # this error probably cannot recover.
                logger.exception(exc)
                logger.error(f"streaming exception: {exc}")
                output_jpeg_bytes = __class__._substitute_image(
                    "Oh no - stream error :(",
                    f"{type(exc).__name__}, no preview from cam. retrying.",
                    appconfig.uisettings.livestream_mirror_effect,
                )

            yield (b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + output_jpeg_bytes + b"\r\n\r\n")

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
        img_draw.text((25, 100), caption, fill=text_fill, font=font_large)
        img_draw.text((25, 120), message, fill=text_fill, font=font_small)
        img_draw.text((25, 140), "please check camera and logs", fill=text_fill, font=font_small)

        # flip if mirror effect is on because messages shall be readable on screen
        if mirror:
            img = ImageOps.mirror(img)

        # create jpeg
        jpeg_buffer = BytesIO()
        img.save(jpeg_buffer, format="jpeg", quality=95)
        return jpeg_buffer.getvalue()

    @staticmethod
    def _load_ffmpeg():
        # load ffmpeg once to have it in memory. otherwise first video might fail because startup time is not respected by implementation
        logger.info("running ffmpeg once to have it in memory later for video use")
        try:
            subprocess.run(args=["ffmpeg", "-version"], timeout=10, check=True, stdout=subprocess.DEVNULL)
        except Exception as exc:
            logger.warning(f"ffmpeg could not be loaded, error: {exc}")
        else:
            # no error, service restart ok
            logger.info("ffmpeg loaded successfully")
