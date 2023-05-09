"""
abstract for the photobooth-app backends
"""
import dataclasses
import json
import logging
import time
from abc import ABC, abstractmethod
from multiprocessing import Condition, Lock, shared_memory

from pymitter import EventEmitter

from ...appconfig import AppConfig

logger = logging.getLogger(__name__)


# retry some times to get image for stream
MAX_ATTEMPTS = 3

#
# Dataclass for stats
#


@dataclasses.dataclass
class BackendStats:
    """
    defines some common stats - if backend supports, they return these properties,
    if not, may be 0 or None
    """

    backend_name: str = __name__
    fps: int = None
    exposure_time_ms: float = None
    lens_position: float = None
    gain: float = None
    lux: float = None
    colour_temperature: int = None
    sharpness: int = None


class AbstractBackend(ABC):
    """
    photobooth-app abstract to create backends.
    """

    @abstractmethod
    def __init__(self, evtbus: EventEmitter, config: AppConfig):
        # public
        self.metadata = {}

        # private
        self._fps = 0

        self._evtbus = evtbus
        self._config = config

        self._evtbus.on("statemachine/on_thrill", self._on_capture_mode)

        self._evtbus.on("onCaptureMode", self._on_capture_mode)
        self._evtbus.on("onPreviewMode", self._on_preview_mode)

        super().__init__()

    def __repr__(self):
        return f"{self.__class__}"

    # @property
    # @abstractmethod
    # def stream_url(self):
    #    """
    #    get the default backend stream
    #    """
    #    pass

    @abstractmethod
    def wait_for_hq_image(self):
        """
        function blocks until high quality image is available
        """

    @abstractmethod
    def start(self):
        """To start the backend to serve"""

    @abstractmethod
    def stop(self):
        """To stop the backend to serve"""

    @abstractmethod
    def stats(self) -> BackendStats:
        """gather backend specific stats

        Returns:
            BackendStats: _description_
        """

    #
    # INTERNAL FUNCTIONS TO BE IMPLEMENTED
    #

    @abstractmethod
    def _wait_for_lores_image(self):
        """
        function blocks until frame is available for preview stream
        """

    @abstractmethod
    def _wait_for_lores_frame(self):
        """
        function blocks until frame is available for autofocus usually
        """

    @abstractmethod
    def _on_capture_mode(self):
        """called externally via events and used to change to a capture mode if necessary"""

    @abstractmethod
    def _on_preview_mode(self):
        """called externally via events and used to change to a preview mode if necessary"""

    #
    # FUNCTIONS IMPLEMENTED IN ABSTRACT CLASS
    #

    def gen_stream(self):
        """
        yield jpeg images to stream to client (if not created otherwise)
        this function may be overriden by backends, but this is the default one
        relies on the backends implementation of _wait_for_lores_image to return a buffer
        """
        logger.info(f"livestream started on backend {self=}")

        last_time = time.time_ns()
        while True:
            for attempt in range(1, MAX_ATTEMPTS + 1):
                try:
                    buffer = self._wait_for_lores_image()
                except TimeoutError:
                    logger.error(
                        "error capture lores image for stream. "
                        f"timeout expired {attempt=}/{MAX_ATTEMPTS}, retrying"
                    )
                    # can we do additional error handling here?
                else:
                    break
            else:
                # we failed finally all the attempts - deal with the consequences.
                logger.critical(
                    "critical error getting stream. "
                    f"failed to get lores image after {MAX_ATTEMPTS} attempts. giving up!"
                )

                # return to signal stop yielding frames to calling function
                return

            now_time = time.time_ns()
            if (now_time - last_time) / 1000**3 >= (
                1 / self._config.common.LIVEPREVIEW_FRAMERATE
            ):
                last_time = now_time

                try:
                    yield (
                        b"--frame\r\n"
                        b"Content-Type: image/jpeg\r\n\r\n" + buffer + b"\r\n\r\n"
                    )

                except GeneratorExit:
                    # TODO: this is not triggered unfortunately. could be useful for cleanup if no stream is
                    # requested any more. otherwise consider delete
                    logger.debug(f"request exit! {self=}")
                    break

    def _publish_sse_initial(self):
        self._publish_sse_metadata()

    def _publish_sse_metadata(self):
        self._evtbus.emit(
            "publishSSE",
            sse_event="frameserver/metadata",
            sse_data=json.dumps(self.metadata),
        )


#
# INTERNAL FUNCTIONS to operate on the shared memory exchanged between processes.
#


@dataclasses.dataclass
class SharedMemoryDataExch:
    """
    bundle data array and it's condition.
    1) save some instance attributes and
    2) bundle as it makes sense
    """

    sharedmemory: shared_memory.SharedMemory = None
    condition: Condition = None
    lock: Lock = None


def decompile_buffer(shm: memoryview) -> bytes:
    """
    decompile buffer holding jpeg buffer for transport between processes
    in shared memory
    constructed as
    INT(4bytes)+JPEG of length the int describes

    Args:
        shm (memoryview): shared memory buffer

    Returns:
        bytes: concat(length of jpeg+jpegbuffer)
    """
    # ATTENTION: shm is a memoryview; sliced variables are also a reference only.
    # means for this app in consequence: here is the place to make a copy
    # of the image for further processing
    # ATTENTION2: this function needs to be called with lock aquired
    length = int.from_bytes(shm.buf[0:4], "big")
    ret: memoryview = shm.buf[4 : length + 4]
    return ret.tobytes()


def compile_buffer(shm: memoryview, jpeg_buffer: bytes) -> bytes:
    """
    compile buffer holding jpeg buffer for transport between processes
    in shared memory
    constructed as
    INT(4bytes)+JPEG of length the int describes

    Args:
        shm (bytes): shared memory buffer
        jpeg_buffer (bytes): jpeg image
    """
    # ATTENTION: shm is a memoryview; sliced variables are also a reference only.
    # means for this app in consequence: here is the place to make a copy
    # of the image for further processing
    # ATTENTION2: this function needs to be called with lock aquired
    length: int = len(jpeg_buffer)
    length_bytes = length.to_bytes(4, "big")
    shm.buf[0:4] = length_bytes
    shm.buf[4 : length + 4] = jpeg_buffer
