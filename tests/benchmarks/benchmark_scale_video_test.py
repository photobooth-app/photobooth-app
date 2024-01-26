import logging
from subprocess import Popen

import pytest
from turbojpeg import TurboJPEG

turbojpeg = TurboJPEG()
logger = logging.getLogger(name=None)


def ffmpeg_h264_scale(tmp_path):
    ffmpeg_subprocess = Popen(
        [
            "ffmpeg",
            "-y",  # overwrite with no questions
            "-i",
            "tests/assets/video.mp4",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-filter:v",
            "scale=500:-2",
            "-movflags",
            "+faststart",
            str(tmp_path / "ffmpeg_h264_scale.mp4"),  # https://docs.python.org/3/library/pathlib.html#operators
        ]
    )
    code = ffmpeg_subprocess.wait()
    if code != 0:
        raise AssertionError("process fail")


def ffmpeg_h265_scale(tmp_path):
    ffmpeg_subprocess = Popen(
        [
            "ffmpeg",
            "-y",  # overwrite with no questions
            "-i",
            "tests/assets/video.mp4",
            "-c:v",
            "libx265",
            "-preset",
            "veryfast",
            "-filter:v",
            "scale=500:-2",
            "-movflags",
            "+faststart",
            str(tmp_path / "ffmpeg_h265_scale.mp4"),  # https://docs.python.org/3/library/pathlib.html#operators
        ]
    )
    code = ffmpeg_subprocess.wait()
    if code != 0:
        raise AssertionError("process fail")


# TODO: # https://engineering.giphy.com/how-to-make-gifs-with-ffmpeg/
def ffmpeg_convertgif_lq_scale(tmp_path):
    ffmpeg_subprocess = Popen(
        [
            "ffmpeg",
            "-y",  # overwrite with no questions
            "-i",
            "tests/assets/video.mp4",
            "-vf",
            "fps=12,scale=500:-2:flags=bicubic",
            str(tmp_path / "ffmpeg_convertgif_lq_scale.gif"),  # https://docs.python.org/3/library/pathlib.html#operators
        ]
    )
    code = ffmpeg_subprocess.wait()
    if code != 0:
        raise AssertionError("process fail")


# TODO: # https://engineering.giphy.com/how-to-make-gifs-with-ffmpeg/
def ffmpeg_convertgif_hq_scale(tmp_path):
    ffmpeg_subprocess = Popen(
        [
            "ffmpeg",
            "-y",  # overwrite with no questions
            "-i",
            "tests/assets/video.mp4",
            "-vf",
            "fps=12,scale=500:-2:flags=bicubic,split[s0][s1];[s0]palettegen[p];[s1][p]paletteuse",
            str(tmp_path / "ffmpeg_convertgif_hq_scale.gif"),  # https://docs.python.org/3/library/pathlib.html#operators
        ]
    )
    code = ffmpeg_subprocess.wait()
    if code != 0:
        raise AssertionError("process fail")


def ffmpeg_convertwebm_vp9_scale(tmp_path):
    ffmpeg_subprocess = Popen(
        [
            "ffmpeg",
            "-y",  # overwrite with no questions
            "-i",
            "tests/assets/video.mp4",
            "-c:v",
            "libvpx-vp9",
            "-crf",
            "30",
            "-b:v",
            "0",
            "-deadline",
            "realtime",
            str(tmp_path / "ffmpeg_convertwebm_vp9_scale.webm"),  # https://docs.python.org/3/library/pathlib.html#operators
        ]
    )
    code = ffmpeg_subprocess.wait()
    if code != 0:
        raise AssertionError("process fail")


def ffmpeg_convertwebm_vp8_scale(tmp_path):
    ffmpeg_subprocess = Popen(
        [
            "ffmpeg",
            "-y",  # overwrite with no questions
            "-i",
            "tests/assets/video.mp4",
            "-c:v",
            "libvpx",
            "-c:a",
            "libvorbis",
            "-b:v",
            "1M",
            str(tmp_path / "ffmpeg_convertwebm_vp8_scale.webm"),  # https://docs.python.org/3/library/pathlib.html#operators
        ]
    )
    code = ffmpeg_subprocess.wait()
    if code != 0:
        raise AssertionError("process fail")


@pytest.mark.benchmark(group="scalevideo")
def test_ffmpeg_h264_scale(benchmark, tmp_path):
    benchmark(ffmpeg_h264_scale, tmp_path=tmp_path)


@pytest.mark.benchmark(group="scalevideo")
def test_ffmpeg_h265_scale(benchmark, tmp_path):
    benchmark(ffmpeg_h265_scale, tmp_path=tmp_path)


@pytest.mark.benchmark(group="scalevideo")
def test_ffmpeg_convertgif_lq_scale(benchmark, tmp_path):
    benchmark(ffmpeg_convertgif_lq_scale, tmp_path=tmp_path)


@pytest.mark.benchmark(group="scalevideo")
def test_ffmpeg_convertgif_hq_scale(benchmark, tmp_path):
    benchmark(ffmpeg_convertgif_hq_scale, tmp_path=tmp_path)


@pytest.mark.benchmark(group="scalevideo")
def test_ffmpeg_convertwebm_vp9_scale(benchmark, tmp_path):
    pytest.skip("this one is so slow, we do not even benchmark")
    benchmark(ffmpeg_convertwebm_vp9_scale, tmp_path=tmp_path)


@pytest.mark.benchmark(group="scalevideo")
def test_ffmpeg_convertwebm_vp8_scale(benchmark, tmp_path):
    pytest.skip("this one is so slow, we do not even benchmark")
    benchmark(ffmpeg_convertwebm_vp8_scale, tmp_path=tmp_path)
