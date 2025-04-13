import logging
from subprocess import Popen

import av
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
            "src/tests/assets/video.mp4",
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
            "src/tests/assets/video.mp4",
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


def pyav_h264_scale(tmp_path, thread_type, threading_number):
    input_container = av.open("src/tests/assets/video.mp4")
    input_stream = input_container.streams.video[0]
    input_stream.thread_type = thread_type  # speed up decoding
    input_stream.thread_count = threading_number
    output_container = av.open(tmp_path / "pyav.mp4", mode="w")
    output_stream = output_container.add_stream("h264", rate=input_stream.codec_context.framerate)  # rate is fps
    output_stream.width = 500
    out_height = int(output_stream.width * (input_stream.height / input_stream.width))
    out_height += out_height % 2  # round up to nearest even number
    output_stream.height = out_height
    output_stream.codec_context.options["movflags"] = "+faststart"
    output_stream.codec_context.options["preset"] = "veryfast"
    output_stream.codec_context.bit_rate = 5000000
    # output_stream.codec_context.profile = "Main"  # print(output_stream.codec_context.profiles) baseline, ...
    output_stream.pix_fmt = "yuv420p"

    for frame in input_container.decode(input_stream):
        # Das Frame in der Zielgröße skalieren
        scaled_frame = frame.reformat(
            width=output_stream.width,
            height=output_stream.height,
            # interpolation=Interpolation.BILINEAR,
        )

        # Das skalierte Frame in den Ausgabestream codieren
        for packet in output_stream.encode(scaled_frame):
            output_container.mux(packet)

    # Restliche Frames flushen
    for packet in output_stream.encode():
        output_container.mux(packet)

    # Container schließen
    input_container.close()
    output_container.close()


def ffmpeg_convertwebm_vp9_scale(tmp_path):
    ffmpeg_subprocess = Popen(
        [
            "ffmpeg",
            "-y",  # overwrite with no questions
            "-i",
            "src/tests/assets/video.mp4",
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
            "src/tests/assets/video.mp4",
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


def ffmpeg_convertavif_scale(tmp_path):
    ffmpeg_subprocess = Popen(
        [
            "ffmpeg",
            "-y",  # overwrite with no questions
            "-i",
            "src/tests/assets/video.mp4",
            "-c:v",
            "libaom-av1",
            "-crf",
            "30",
            str(tmp_path / "ffmpeg_convertavif_scale.mkv"),  # https://docs.python.org/3/library/pathlib.html#operators
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


@pytest.fixture(params=["NONE", "AUTO", "FRAME", "SLICE"])
def thread_type(request):
    yield request.param


@pytest.fixture(params=[0, 16])
def threading_number(request):
    yield request.param


@pytest.mark.benchmark(group="scalevideo")
def test_pyav_scale(benchmark, tmp_path, thread_type, threading_number):
    benchmark(pyav_h264_scale, tmp_path, thread_type, threading_number)


@pytest.mark.benchmark(group="scalevideo")
def test_ffmpeg_convertwebm_vp9_scale(benchmark, tmp_path):
    pytest.skip("this one is so slow, we do not even benchmark")
    benchmark(ffmpeg_convertwebm_vp9_scale, tmp_path=tmp_path)


@pytest.mark.benchmark(group="scalevideo")
def test_ffmpeg_convertwebm_vp8_scale(benchmark, tmp_path):
    pytest.skip("this one is so slow, we do not even benchmark")
    benchmark(ffmpeg_convertwebm_vp8_scale, tmp_path=tmp_path)


@pytest.mark.benchmark(group="scalevideo")
def test_ffmpeg_convertavif_scale(benchmark, tmp_path):
    pytest.skip("this one is so slow, we do not even benchmark")
    benchmark(ffmpeg_convertavif_scale, tmp_path=tmp_path)
