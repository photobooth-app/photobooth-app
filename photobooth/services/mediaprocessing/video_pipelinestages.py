import logging
import os
import subprocess
import uuid
from pathlib import Path

logger = logging.getLogger(__name__)

# call ffmpeg command to create boomerang
# ffmpeg -i input_loop.mp4 -filter_complex "[0]reverse[r];[0][r]concat,loop=5:250,setpts=N/55/TB" output_looped_video.mp4

# https://www.bannerbear.com/blog/how-to-make-instagrams-boomerang-effect-with-ffmpeg/
# ffmpeg -i input.mp4 -filter_complex "[0:v]reverse[r];[0:v][r]concat=n=2:v=1[outv]" -map "[outv]" output.mp4
# ffmpeg -i output.mp4 -vf "setpts=1/2*PTS" output_fast.mp4

# https://video.stackexchange.com/a/12906
# ffmpeg -stream_loop 3 -i .\output_looped_video.mp4 -c copy output-stream.mp4

# https://medium.com/@caglarispirli/make-boomerang-w-single-ffmpeg-command-ae6c672acb7
# ffmpeg -i avmsakini_story.mp4 -filter_complex “[0]trim=start=3.5:end=5.5,setpts=0.5*PTS-STARTPTS,split[out0][out1];[out0]reverse[r];[out1][r]concat,loop=2:250,setpts=N/25/TB[out]” -map [out] out4.mp4


def boomerang_stage(video_in: Path) -> Path:
    """
    ffmpeg -i [input path] -vf reverse -af areverse [dest path]
    """

    # generate temp filename to record to
    mp4_output_filepath = Path("tmp", f"boomerang_{uuid.uuid4().hex}").with_suffix(".mp4")

    command_general_options = [
        "-hide_banner",
        "-loglevel",
        "info",
        "-y",
    ]
    command_video_input = [
        "-i",
        str(video_in),
    ]
    command_video_output = [
        "-filter_complex",
        "[0:v]reverse[r];[0:v][r]concat=n=2:v=1[outv]",
        "-map",
        "[outv]",
        "-movflags",
        "+faststart",
    ]

    ffmpeg_command = ["ffmpeg"] + command_general_options + command_video_input + command_video_output + [str(mp4_output_filepath)]
    try:
        subprocess.run(
            args=ffmpeg_command,
            check=True,
            env=dict(os.environ, FFREPORT="file=./log/ffmpeg-boomerang-last.log:level=32"),
        )
    except Exception as exc:
        logger.exception(exc)
        raise RuntimeError(f"error processing boomerang video, error: {exc}") from exc
    else:
        return mp4_output_filepath
