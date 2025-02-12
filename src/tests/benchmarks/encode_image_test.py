import io
import logging

import cv2
import pytest
import pyvips
import simplejpeg
from PIL import Image
from turbojpeg import TurboJPEG

turbojpeg = TurboJPEG()
logger = logging.getLogger(name=None)


## encode frame to jpeg comparison


def pyvips_encode(frame_from_camera):
    # mute some other logger, by raising their debug level to INFO
    lgr = logging.getLogger(name="pyvips")
    lgr.setLevel(logging.WARNING)
    lgr.propagate = True
    # frame_from_camera = cv2.cvtColor(frame_from_camera, cv2.COLOR_BGR2RGB)
    out = pyvips.Image.new_from_array(frame_from_camera)
    bytes = out.write_to_buffer(".jpg[Q=85]")  # type: ignore
    # im = Image.open(io.BytesIO(bytes))
    # im.show()

    return bytes


def turbojpeg_encode(frame_from_camera):
    # encoding BGR array to output.jpg with default settings.
    # 85=default quality
    bytes = turbojpeg.encode(frame_from_camera, quality=85)

    return bytes


def pillow_encode_jpg(frame_from_camera):
    image = Image.fromarray(frame_from_camera.astype("uint8"), "RGB")
    byte_io = io.BytesIO()
    image.save(byte_io, format="JPEG", quality=85)
    bytes_full = byte_io.getbuffer()

    return bytes_full


def cv2_encode_jpg(frame_from_camera):
    encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), 90]
    result, encimg = cv2.imencode(".jpg", frame_from_camera, encode_param)

    return encimg.tobytes()


def cv2_encode_webp(frame_from_camera):
    encode_param = [int(cv2.IMWRITE_WEBP_QUALITY), 90]
    result, encimg = cv2.imencode(".webp", frame_from_camera, encode_param)

    return encimg.tobytes()


def cv2_encode_png(frame_from_camera):
    encode_param = [int(cv2.IMWRITE_PNG_COMPRESSION), 1]
    # For PNG, it can be the compression level from 0 to 9. A higher value means a smaller size and longer compression time.
    # If specified, strategy is changed to IMWRITE_PNG_STRATEGY_DEFAULT (Z_DEFAULT_STRATEGY).
    # Default value is 1 (best speed setting).
    result, encimg = cv2.imencode(".png", frame_from_camera, encode_param)

    return encimg.tobytes()


def simplejpeg_encode(frame_from_camera):
    # picamera2 uses PIL under the hood. so if this is fast on a PI,
    # we might be able to remove turbojpeg from dependencies on win/other linux because scaling could be done in PIL sufficiently fast
    # encoding BGR array to output.jpg with default settings.
    # 85=default quality
    # simplejpeg uses turbojpeg as lib, but pyturbojpeg also has scaling
    bytes = simplejpeg.encode_jpeg(frame_from_camera, quality=85, fastdct=True)

    return bytes


def pillow_encode_png(frame_from_camera):
    # compress_level=1 saves pngs much faster, and still gets most of the compression.
    image = Image.fromarray(frame_from_camera.astype("uint8"), "RGB")
    byte_io = io.BytesIO()
    image.save(byte_io, format="PNG", quality=85, compress_level=1)
    bytes_full = byte_io.getbuffer()

    return bytes_full


def pillow_encode_webp(frame_from_camera):
    # compress_level=1 saves pngs much faster, and still gets most of the compression.
    image = Image.fromarray(frame_from_camera.astype("uint8"), "RGB")
    byte_io = io.BytesIO()
    image.save(byte_io, format="webp", quality=80, lossless=False)
    bytes_full = byte_io.getbuffer()

    return bytes_full


@pytest.fixture(
    params=[
        "turbojpeg_encode",
        "pillow_encode_jpg",
        "cv2_encode_jpg",
        "cv2_encode_webp",
        "cv2_encode_png",
        "simplejpeg_encode",
        "pyvips_encode",
        "pillow_encode_png",
        "pillow_encode_webp",
    ]
)
def library(request):
    # yield fixture instead return to allow for cleanup:
    yield request.param

    # cleanup
    # os.remove(request.param)


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
    benchmark(eval(library), frame_from_camera=image_lores)
    assert True


# needs pip install pytest-benchmark
@pytest.mark.benchmark(group="encode_hires")
def test_libraries_encode_hires(library, image_hires, benchmark):
    benchmark(eval(library), frame_from_camera=image_hires)
    assert True
