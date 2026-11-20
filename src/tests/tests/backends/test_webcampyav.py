import logging
import weakref
from collections.abc import Generator, Iterator
from contextlib import closing
from typing import cast

import av
import pytest
from av.container import InputContainer

from photobooth.services.backends.webcampyav import WebcamPyavBackend
from photobooth.services.config.groups.cameras import GroupCameraPyav
from photobooth.utils.enumerate import webcameras

from ..util import block_until_device_is_running, get_images

logger = logging.getLogger(name=None)


def test_frame_generator_closes_demuxer():
    class FakePacket:
        pass

    class FakeDemuxer(Iterator[av.Packet]):
        closed = False
        packet_ref: weakref.ReferenceType[FakePacket] | None = None

        def __iter__(self) -> Iterator[av.Packet]:
            return self

        def __next__(self) -> av.Packet:
            packet = FakePacket()
            self.packet_ref = weakref.ref(packet)
            return cast(av.Packet, packet)

        def close(self) -> None:
            self.closed = True

    class FakeInputDevice:
        def __init__(self, demuxer: FakeDemuxer):
            self.demuxer = demuxer

        def demux(self, input_stream: av.VideoStream) -> Iterator[av.Packet]:
            return self.demuxer

    demuxer = FakeDemuxer()
    backend = WebcamPyavBackend(GroupCameraPyav())
    packets = backend.frame_generator(cast(InputContainer, FakeInputDevice(demuxer)), cast(av.VideoStream, object()))

    with closing(packets):
        next(packets)

    assert demuxer.closed
    assert demuxer.packet_ref is not None
    assert demuxer.packet_ref() is None


@pytest.fixture(scope="module")
def backend_pyav() -> Generator[WebcamPyavBackend, None, None]:
    # setup
    backend = WebcamPyavBackend(GroupCameraPyav())

    logger.info("probing for available cameras")
    avail_cams = webcameras()
    if not avail_cams:
        pytest.skip("no camera found, skipping test")

    cameraIndex = avail_cams[0]

    logger.info(f"available camera indexes: {avail_cams}")
    logger.info(f"using first camera index to test: {cameraIndex}")

    backend._config.device_identifier = cameraIndex
    # select a low resolution that all cameras are capable of
    backend._config.cam_resolution_width = 640
    backend._config.cam_resolution_height = 480
    # backend._config.cam_framerate = 30

    # deliver
    backend.start()
    block_until_device_is_running(backend)
    yield backend
    backend.stop()


def test_optimize_mode(backend_pyav: WebcamPyavBackend):
    backend_pyav._handle_switchmode_still_mode()
    backend_pyav._handle_switchmode_video_mode()
    backend_pyav._handle_switchmode_standby()


def test_get_images_webcampyav(backend_pyav: WebcamPyavBackend):
    """get lores and hires images from backend and assert"""
    get_images(backend_pyav)
