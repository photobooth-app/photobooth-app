import io
import logging
from subprocess import PIPE, Popen

import cv2
import numpy
import pytest
import pyvips
from PIL import Image
from turbojpeg import TurboJPEG

turbojpeg = TurboJPEG()
logger = logging.getLogger(name=None)


def ffmpeg_scale(jpeg_bytes, tmp_path):
    ffmpeg_subprocess = Popen(
        [
            "ffmpeg",
            "-y",  # overwrite with no questions
            "-f",  # force input or output format
            "image2pipe",
            "-i",
            "-",
            "-vf",
            "scale='iw/2:ih/2'",  # bicubic
            str(tmp_path / "tmpOut.jpg"),  # https://docs.python.org/3/library/pathlib.html#operators
        ],
        stdin=PIPE,
    )
    ffmpeg_subprocess.stdin.write(jpeg_bytes)
    ffmpeg_subprocess.stdin.close()
    code = ffmpeg_subprocess.wait()
    if code != 0:
        raise AssertionError("process fail")


def pyvips_scale(jpeg_bytes, tmp_path):
    # mute some other logger, by raising their debug level to INFO
    lgr = logging.getLogger(name="pyvips")
    lgr.setLevel(logging.WARNING)
    lgr.propagate = True

    image = pyvips.Image.new_from_buffer(jpeg_bytes, "")
    out: pyvips.Image = image.thumbnail_image(
        int(image.width / 2),  # width
    )
    bytes = out.jpegsave_buffer(Q=85)

    return bytes


def pyvips_resize_scale(jpeg_bytes, tmp_path):
    # mute some other logger, by raising their debug level to INFO
    lgr = logging.getLogger(name="pyvips")
    lgr.setLevel(logging.WARNING)
    lgr.propagate = True

    image = pyvips.Image.new_from_buffer(jpeg_bytes, "")
    out: pyvips.Image = image.resize(0.5)
    bytes = out.jpegsave_buffer(Q=85)
    # im = Image.open(io.BytesIO(bytes))
    # im.show()

    return bytes


def turbojpeg_scale(jpeg_bytes, tmp_path):
    # encoding BGR array to output.jpg with default settings.
    # 85=default quality
    bytes = turbojpeg.scale_with_quality(jpeg_bytes, quality=85, scaling_factor=(1, 2))

    return bytes


def pillow_scale(jpeg_bytes, tmp_path):
    # read image
    image = Image.open(io.BytesIO(jpeg_bytes))

    # scale by 0.5

    scale_percent = 50  # percent of original size
    width = int(image.width * scale_percent / 100)
    height = int(image.height * scale_percent / 100)
    dim = (width, height)
    # https://pillow.readthedocs.io/en/latest/handbook/concepts.html#filters-comparison-table
    image.thumbnail(dim, Image.Resampling.BICUBIC)  # bicubic for comparison

    # encode to jpeg again
    byte_io = io.BytesIO()
    image.save(byte_io, format="JPEG", quality=85)
    bytes_full = byte_io.getbuffer()

    return bytes_full


def cv2_scale(jpeg_bytes, tmp_path):
    # convert to cv2 format that can be resized by cv2
    nparr = numpy.frombuffer(jpeg_bytes, numpy.uint8)
    img_np = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    scale_percent = 50  # percent of original size
    width = int(img_np.shape[1] * scale_percent / 100)
    height = int(img_np.shape[0] * scale_percent / 100)
    dim = (width, height)

    # resize image
    img_np_resized = cv2.resize(img_np, dim, interpolation=cv2.INTER_AREA)

    # and encode to jpeg again
    encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), 90]
    result, encimg = cv2.imencode(".jpg", img_np_resized, encode_param)

    return encimg


@pytest.fixture(params=["turbojpeg_scale", "pillow_scale", "cv2_scale", "pyvips_scale", "pyvips_resize_scale", "ffmpeg_scale"])
def library(request):
    # yield fixture instead return to allow for cleanup:
    yield request.param


def image(file) -> bytes:
    with open(file, "rb") as file:
        in_file_read = file.read()

    return in_file_read


@pytest.fixture()
def image_hires() -> bytes:
    yield image("tests/assets/input.jpg")


@pytest.fixture()
def image_lores() -> bytes:
    yield image("tests/assets/input_lores.jpg")


# needs pip install pytest-benchmark
@pytest.mark.benchmark(
    group="scalejpeg_hires",
)
def test_libraries_encode_hires(library, image_hires, benchmark, tmp_path):
    benchmark(eval(library), jpeg_bytes=image_hires, tmp_path=tmp_path)
    assert True


# needs pip install pytest-benchmark
@pytest.mark.benchmark(
    group="scalejpeg_lores",
)
def test_libraries_encode_lores(library, image_lores, benchmark, tmp_path):
    benchmark(eval(library), jpeg_bytes=image_lores, tmp_path=tmp_path)
    assert True
