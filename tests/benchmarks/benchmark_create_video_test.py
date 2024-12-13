import logging
import time
from subprocess import PIPE, Popen

import pytest

from photobooth.services.config import appconfig

logger = logging.getLogger(name=None)


@pytest.fixture(autouse=True)
def run_around_tests():
    appconfig.reset_defaults()

    yield


def process_pyav(tmp_path):
    pass


# basic idea from https://stackoverflow.com/a/42602576
def process_ffmpeg(tmp_path):
    logger.info("popen")
    tms = time.time()
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
            str(tmp_path / "ffmpeg_scale.mp4"),
        ],
        stdin=PIPE,
    )
    logger.info("popen'ed")
    logger.debug(f"-- process time: {round((time.time() - tms), 2)}s ")

    tms = time.time()
    with open("tests/assets/input_lores.jpg", "rb") as file:
        in_file_read = file.read()

        for _ in range(200):
            ffmpeg_subprocess.stdin.write(in_file_read)
            ffmpeg_subprocess.stdin.flush()
    logger.info("all written")
    logger.debug(f"-- process time: {round((time.time() - tms), 2)}s ")

    # release finish video processing
    tms = time.time()
    ffmpeg_subprocess.stdin.close()
    logger.info("stdin closed")
    logger.debug(f"-- process time: {round((time.time() - tms), 2)}s ")

    # now postproccess, but app can continue.
    tms = time.time()
    code = ffmpeg_subprocess.wait()
    logger.info("finished waiting.")
    logger.debug(f"-- process time: {round((time.time() - tms), 2)}s ")
    if code != 0:
        # more debug info can be received in ffmpeg popen stderr (pytest captures automatically)
        # TODO: check how to get in application at runtime to write to logs or maybe let ffmpeg write separate logfile
        raise RuntimeError(f"error creating videofile, ffmpeg exit code ({code}).")


@pytest.mark.benchmark(group="create_video_from_pipe_to_h264")
def test_process_ffmpeg(benchmark, tmp_path):
    benchmark(process_ffmpeg, tmp_path=tmp_path)


@pytest.mark.benchmark(group="create_video_from_pipe_to_h264")
def test_process_pyav(benchmark, tmp_path):
    benchmark(process_pyav, tmp_path=tmp_path)
