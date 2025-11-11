import io
import logging
from pathlib import Path
from subprocess import PIPE, Popen

import pytest
from PIL import Image, ImageSequence
from turbojpeg import TurboJPEG

from ..tests.util import dummy_animation

turbojpeg = TurboJPEG()
logger = logging.getLogger(name=None)


def ffmpeg_hq_optimizedquality_scale(gif_filepath: Path, tmp_path):
    # https://engineering.giphy.com/how-to-make-gifs-with-ffmpeg/
    ffmpeg_subprocess = Popen(
        [
            "ffmpeg",
            "-y",  # overwrite with no questions
            "-i",
            str(gif_filepath),
            "-vf",
            "scale=500:-1:flags=lanczos,split[s0][s1];[s0]palettegen[p];[s1][p]paletteuse",
            str(tmp_path / "ffmpeg_hq_optimizedquality_scale.gif"),  # https://docs.python.org/3/library/pathlib.html#operators
        ]
    )
    code = ffmpeg_subprocess.wait()
    if code != 0:
        raise AssertionError("process fail")


def ffmpeg_hq_optimizedspeed_scale(gif_filepath: Path, tmp_path):
    # https://engineering.giphy.com/how-to-make-gifs-with-ffmpeg/
    ffmpeg_subprocess = Popen(
        [
            "ffmpeg",
            "-y",  # overwrite with no questions
            "-i",
            str(gif_filepath),
            "-vf",
            "scale=500:-1:flags=bicubic,split[s0][s1];[s0]palettegen[p];[s1][p]paletteuse",
            str(tmp_path / "ffmpeg_hq_optimizedspeed_scale.gif"),  # https://docs.python.org/3/library/pathlib.html#operators
        ]
    )
    code = ffmpeg_subprocess.wait()
    if code != 0:
        raise AssertionError("process fail")


def ffmpeg_stdin_scale(gif_filepath: Path, tmp_path):
    ffmpeg_subprocess = Popen(
        [
            "ffmpeg",
            "-y",  # overwrite with no questions
            "-f",  # force input or output format
            "image2pipe",
            "-i",
            "-",
            "-vf",
            "scale=500:-1:flags=bicubic,split[s0][s1];[s0]palettegen[p];[s1][p]paletteuse",
            str(tmp_path / "ffmpeg_stdin_scale.gif"),  # https://docs.python.org/3/library/pathlib.html#operators
        ],
        stdin=PIPE,
    )
    assert ffmpeg_subprocess.stdin
    ffmpeg_subprocess.stdin.write(gif_filepath.read_bytes())
    ffmpeg_subprocess.stdin.close()
    code = ffmpeg_subprocess.wait()
    if code != 0:
        raise AssertionError("process fail")


def pil_scale(gif_filepath: Path, tmp_path):
    gif_image = Image.open(gif_filepath, formats=["gif"])

    # Wrap on-the-fly thumbnail generator
    def thumbnails(frames: ImageSequence.Iterator):
        for frame in frames:
            thumbnail = frame.copy()
            thumbnail.thumbnail(size=target_size, resample=Image.Resampling.BICUBIC)
            yield thumbnail

    # to recover the original durations in scaled versions
    durations = []
    for frame in ImageSequence.Iterator(gif_image):
        frame.load()
        duration = frame.info.get("duration", 1000)  # fallback 1sec if info not avail.
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


@pytest.fixture(
    params=[
        "pil_scale",
        "ffmpeg_stdin_scale",
        "ffmpeg_hq_optimizedquality_scale",
        "ffmpeg_hq_optimizedspeed_scale",
    ]
)
def library(request):
    # yield fixture instead return to allow for cleanup:
    yield request.param


def image(file) -> bytes:
    with open(file, "rb") as file:
        in_file_read = file.read()

    return in_file_read


@pytest.mark.benchmark(
    group="scalegif",
)
def test_libraries_scalegif(library, benchmark, tmp_path):
    dummy_animation_file = tmp_path / "in_animation.gif"
    dummy_animation(dummy_animation_file)
    benchmark(eval(library), gif_filepath=dummy_animation_file, tmp_path=tmp_path)
    assert True
