import io
import logging

import pytest
import pyvips
from PIL import Image, ImageSequence
from turbojpeg import TurboJPEG

from photobooth.services.config import appconfig

turbojpeg = TurboJPEG()
logger = logging.getLogger(name=None)


@pytest.fixture(autouse=True)
def run_around_tests():
    appconfig.reset_defaults()

    yield


def pyvips_scale(gif_bytes):
    # mute some other logger, by raising their debug level to INFO
    lgr = logging.getLogger(name="pyvips")
    lgr.setLevel(logging.WARNING)
    lgr.propagate = True

    out = pyvips.Image.thumbnail_buffer(gif_bytes, 500, option_string="n=-1")
    bytes = out.gifsave_buffer()

    return bytes


def pil_scale(gif_bytes):
    gif_image = Image.open(io.BytesIO(gif_bytes), formats=["gif"])

    # Wrap on-the-fly thumbnail generator
    def thumbnails(frames: list[Image.Image]):
        for frame in frames:
            thumbnail = frame.copy()
            thumbnail.thumbnail(size=target_size, resample=Image.Resampling.LANCZOS)
            yield thumbnail

    # to recover the original durations in scaled versions
    durations = []
    for i in range(gif_image.n_frames):
        gif_image.seek(i)
        duration = gif_image.info.get("duration", 1000)  # fallback 1sec if info not avail.
        durations.append(duration)

    # determine target size
    target_size = (500, 500)

    # Get sequence iterator
    frames = ImageSequence.Iterator(gif_image)
    resized_frames = thumbnails(frames)

    # Save output
    out = io.BytesIO()
    om = next(resized_frames)  # Handle first frame separately
    om.info = gif_image.info  # Copy original information (duration is only for first frame so on save handled separately)
    om.save(
        out,
        format="gif",
        save_all=True,
        append_images=list(resized_frames),
        duration=durations,
        optimize=True,
        loop=0,  # loop forever
    )

    return out.getvalue()


@pytest.fixture(params=["pyvips_scale", "pil_scale"])
def library(request):
    # yield fixture instead return to allow for cleanup:
    yield request.param


def image(file) -> bytes:
    with open(file, "rb") as file:
        in_file_read = file.read()

    return in_file_read


@pytest.mark.benchmark()
def test_libraries_scalegif(library, benchmark):
    benchmark(eval(library), gif_bytes=image("tests/assets/animation.gif"))
    assert True
