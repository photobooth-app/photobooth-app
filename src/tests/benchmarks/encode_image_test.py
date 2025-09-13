import io
import logging

import cv2
import pytest
import simplejpeg
from PIL import Image
from turbojpeg import TurboJPEG

turbojpeg = TurboJPEG()
logger = logging.getLogger(name=None)
inplace_buffer = None


## encode frame to jpeg comparison


def turbojpeg_encode(frame_from_camera):
    # encoding BGR array to output.jpg with default settings.
    # 85=default quality
    bytes = turbojpeg.encode(frame_from_camera, quality=85)

    return bytes


def turbojpeg_inplace_encode(frame_from_camera):
    global inplace_buffer

    if inplace_buffer is None:
        buffer_size = turbojpeg.buffer_size(frame_from_camera)
        inplace_buffer = bytearray(buffer_size)
    # encoding BGR array to output.jpg with default settings.
    # 85=default quality

    # in-place encoding with default settings.
    # buffer_size = turbojpeg.buffer_size(frame_from_camera)
    # dest_buf = bytearray(buffer_size)
    result, n_byte = turbojpeg.encode(frame_from_camera, dst=inplace_buffer)

    # return value is the dest_buf argument value
    assert id(result) == id(inplace_buffer)

    # out_file = open("output.jpg", "wb")
    # out_file.write(inplace_buffer[:n_byte])
    # out_file.close()

    # quit()
    return inplace_buffer[:n_byte]


def pillow_encode_jpg(frame_from_camera):
    image = Image.fromarray(frame_from_camera.astype("uint8"))
    byte_io = io.BytesIO()
    image.save(byte_io, format="JPEG", quality=85)
    bytes_full = byte_io.getbuffer()

    return bytes_full


def cv2_encode_jpg(frame_from_camera):
    encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), 90]
    result, encimg = cv2.imencode(".jpg", frame_from_camera, encode_param)

    return encimg.tobytes()


def simplejpeg_encode(frame_from_camera):
    # picamera2 uses PIL under the hood. so if this is fast on a PI,
    # we might be able to remove turbojpeg from dependencies on win/other linux because scaling could be done in PIL sufficiently fast
    # encoding BGR array to output.jpg with default settings.
    # 85=default quality
    # simplejpeg uses turbojpeg as lib, but pyturbojpeg also has scaling
    bytes = simplejpeg.encode_jpeg(frame_from_camera, quality=85, fastdct=True)

    return bytes


def turbojpeg_yuv420_encode(frame_from_camera, rH, rW):
    jpeg_bytes = turbojpeg.encode_from_yuv(frame_from_camera, rH, rW, quality=85)
    # im = Image.open(io.BytesIO(jpeg_bytes))
    # im.save("test_yuv420_turbojpeg.jpg")
    # quit()
    return jpeg_bytes


def simplejpeg_yuv420_encode(frame_from_camera, rH, rW):
    jpeg_bytes = simplejpeg.encode_jpeg_yuv_planes(
        Y=frame_from_camera[:rH],
        U=frame_from_camera.reshape(rH * 3, rW // 2)[rH * 2 : rH * 2 + rH // 2],
        V=frame_from_camera.reshape(rH * 3, rW // 2)[rH * 2 + rH // 2 :],
        quality=85,
        fastdct=True,
    )
    # im = Image.open(io.BytesIO(jpeg_bytes))
    # im.save("test_yuv420_simplejpeg.jpg")
    # quit()
    return jpeg_bytes


@pytest.fixture(
    params=[
        "turbojpeg_encode",
        "turbojpeg_inplace_encode",
        "pillow_encode_jpg",
        "cv2_encode_jpg",
        "simplejpeg_encode",
    ]
)
def library(request):
    yield request.param


@pytest.fixture(
    params=[
        "turbojpeg_yuv420_encode",
        "simplejpeg_yuv420_encode",
    ]
)
def library_yuv420(request):
    yield request.param


def image(file):
    with open(file, "rb") as file:
        in_file_read = file.read()
        frame_from_camera = turbojpeg.decode(in_file_read)

    # yield fixture instead return to allow for cleanup:
    return frame_from_camera


@pytest.fixture()
def image_lores():
    yield image("src/tests/assets/input_lores.jpg")


@pytest.fixture()
def image_hires():
    yield image("src/tests/assets/input.jpg")


# needs pip install pytest-benchmark
@pytest.mark.benchmark(group="encode_lores")
def test_libraries_encode_lores(library, image_lores, benchmark):
    global inplace_buffer
    inplace_buffer = None
    benchmark(eval(library), frame_from_camera=image_lores)
    assert True


# needs pip install pytest-benchmark
@pytest.mark.benchmark(group="encode_hires")
def test_libraries_encode_hires(library, image_hires, benchmark):
    global inplace_buffer
    inplace_buffer = None
    benchmark(eval(library), frame_from_camera=image_hires)
    assert True


@pytest.mark.benchmark(group="encode_lores")
def test_yuv420_encode_lores(library_yuv420, image_lores, benchmark):
    global inplace_buffer
    inplace_buffer = None
    yuv_frame = cv2.cvtColor(image_lores, cv2.COLOR_BGR2YUV_I420)
    benchmark(eval(library_yuv420), frame_from_camera=yuv_frame, rH=image_lores.shape[0], rW=image_lores.shape[1])
    assert True


@pytest.mark.benchmark(group="encode_hires")
def test_yuv420_encode_hires(library_yuv420, image_hires, benchmark):
    global inplace_buffer
    inplace_buffer = None
    yuv_frame = cv2.cvtColor(image_hires, cv2.COLOR_BGR2YUV_I420)
    benchmark(eval(library_yuv420), frame_from_camera=yuv_frame, rH=image_hires.shape[0], rW=image_hires.shape[1])
    assert True
