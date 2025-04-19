import logging
from subprocess import PIPE, Popen

import av
import pytest

from photobooth.appconfig import appconfig

logger = logging.getLogger(name=None)


@pytest.fixture(autouse=True)
def run_around_tests():
    appconfig.reset_defaults()

    yield


def process_pyav(tmp_path):
    # https://pyav.basswood-io.com/docs/stable/cookbook/numpy.html#generating-video

    input = av.open("src/tests/assets/input_lores.jpg")
    frame_input = next(input.decode())

    container = av.open(tmp_path / "pyav.mp4", mode="w")

    stream = container.add_stream("h264", rate=25)
    stream.width = frame_input.width
    stream.height = frame_input.height
    # stream.pix_fmt = "yuv420p"
    stream.codec_context.options["movflags"] = "faststart"
    stream.codec_context.options["preset"] = "veryfast"
    # stream.codec_context.options["tune"] = "zerolatency"
    # stream.codec_context.profile = "Main"
    stream.codec_context.bit_rate = 2500000

    for _ in range(200):
        for packet in stream.encode(frame_input):
            container.mux(packet)

    # Flush stream
    for packet in stream.encode():
        container.mux(packet)

    # Close the file
    container.close()


# basic idea from https://stackoverflow.com/a/42602576
def process_ffmpeg(tmp_path):
    ffmpeg_subprocess = Popen(
        [
            "ffmpeg",
            "-use_wallclock_as_timestamps",
            "1",
            "-y",  # overwrite with no questions
            "-loglevel",
            "info",
            "-f",  # force input or output format
            "image2pipe",
            "-vcodec",
            "mjpeg",
            "-i",
            "-",
            "-vcodec",
            "libx264",  # warning! image height must be divisible by 2! #there are also hw encoder avail: https://stackoverflow.com/questions/50693934/different-h264-encoders-in-ffmpeg
            "-preset",
            "veryfast",
            "-b:v",  # bitrate
            "5000k",
            "-movflags",
            "+faststart",
            str(tmp_path / "ffmpeg.mp4"),
        ],
        stdin=PIPE,
    )
    assert ffmpeg_subprocess.stdin

    with open("src/tests/assets/input_lores.jpg", "rb") as file:
        in_file_read = file.read()

        for _ in range(200):
            ffmpeg_subprocess.stdin.write(in_file_read)
            ffmpeg_subprocess.stdin.flush()

    # release finish video processing
    ffmpeg_subprocess.stdin.close()

    # now postproccess, but app can continue.
    code = ffmpeg_subprocess.wait()
    if code != 0:
        raise RuntimeError(f"error creating videofile, ffmpeg exit code ({code}).")


@pytest.mark.benchmark(group="create_video_from_pipe_to_h264")
def test_process_ffmpeg(benchmark, tmp_path):
    benchmark(process_ffmpeg, tmp_path=tmp_path)


@pytest.mark.benchmark(group="create_video_from_pipe_to_h264")
def test_process_pyav(benchmark, tmp_path):
    benchmark(process_pyav, tmp_path=tmp_path)
