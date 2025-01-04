"""
Handle all media collection related functions
"""

import logging
import os
import subprocess
from pathlib import Path
from threading import Lock

from PIL import Image, ImageOps, ImageSequence, UnidentifiedImageError

from ... import CACHE_PATH, LOG_PATH
from ...database.models import DimensionTypes
from ..config import appconfig

logger = logging.getLogger(__name__)
resize_lock = Lock()


MAP_DIMENSION_TO_PIXEL = {
    DimensionTypes.full: appconfig.mediaprocessing.full_still_length,
    DimensionTypes.preview: appconfig.mediaprocessing.preview_still_length,
    DimensionTypes.thumbnail: appconfig.mediaprocessing.thumbnail_still_length,
}


def resize_jpeg(filepath_in: Path, filepath_out: Path, scaled_min_length: int):
    """scale a jpeg buffer to another buffer using cv2"""

    image = Image.open(filepath_in)
    ImageOps.exif_transpose(image, in_place=True)

    # scale by 0.5
    original_length = max(image.width, image.height)  # scale for the max length
    scaling_factor = scaled_min_length / original_length

    width = int(image.width * scaling_factor)
    height = int(image.height * scaling_factor)
    dim = (width, height)
    # https://pillow.readthedocs.io/en/latest/handbook/concepts.html#filters-comparison-table
    image.thumbnail(dim, Image.Resampling.BICUBIC)  # bicubic for comparison, does not upscale, which is what we want.

    # encode to jpeg again
    image.save(filepath_out, quality=85)


def resize_gif(filepath_in: Path, filepath_out: Path, scaled_min_length: int):
    """scale a gif image sequence to another buffer using PIL"""
    try:
        gif_image = Image.open(filepath_in, formats=["gif"])
    except (UnidentifiedImageError, Exception) as exc:
        logger.error(f"loading gif failed: {exc}")
        raise RuntimeError(f"filetype not supported, error: {exc}") from exc

    # Wrap on-the-fly thumbnail generator
    def thumbnails(frames: list[Image.Image], target_size: tuple[float, float]):
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

    # Get sequence iterator
    frames = ImageSequence.Iterator(gif_image)
    resized_frames = thumbnails(frames, [scaled_min_length, scaled_min_length])

    # Save output
    om = next(resized_frames)  # Handle first frame separately
    om.info = gif_image.info  # Copy original information (duration is only for first frame so on save handled separately)
    om.save(
        filepath_out,
        format="gif",
        save_all=True,
        append_images=list(resized_frames),
        duration=durations,
        optimize=True,
        loop=0,  # loop forever
    )


def resize_mp4(filepath_in: Path, filepath_out: Path, scaled_min_length: int):
    """ """

    command_general_options = [
        "-hide_banner",
        "-loglevel",
        "info",
        "-y",
    ]
    command_video_input = [
        "-i",
        str(filepath_in),
    ]
    command_video_output = [
        # no upscaling, divisible by 2 for further codec processing
        "-filter:v",
        f"scale=w={scaled_min_length}:h={scaled_min_length}:force_original_aspect_ratio=decrease:force_divisible_by=2",
        "-sws_flags",
        "fast_bilinear",
        "-movflags",
        "+faststart",
    ]

    ffmpeg_command = ["ffmpeg"] + command_general_options + command_video_input + command_video_output + [str(filepath_out)]
    try:
        subprocess.run(
            args=ffmpeg_command,
            check=True,
            env=dict(os.environ, FFREPORT=f"file={LOG_PATH}/ffmpeg-resize-last.log:level=32"),
        )
    except Exception as exc:
        logger.exception(exc)
        logger.warning("please check logfile /log/ffmpeg-resize-last.log for additional errors")
        raise RuntimeError(f"error resizing video, error: {exc}") from exc


def get_resized_filepath(filepath: Path, scaled_min_length: int):
    def get_cached_filepath(filepath: Path, scaled_min_length: int):
        # rebase to: cache-dir/length/original_filename
        relative_path = filepath.absolute().relative_to(Path.cwd())
        cache_filepath = Path(CACHE_PATH, str(scaled_min_length), relative_path)

        os.makedirs(cache_filepath.parent, exist_ok=True)

        return cache_filepath

    # cache is simple: filename+target_length is used to check if file exists, if not, create it.
    cache_filepath = get_cached_filepath(filepath, scaled_min_length)

    # lock to ensure exists-check is valid and only one resize is invoked.
    with resize_lock:
        if cache_filepath.exists():
            # cached version exists - return it.
            # TODO: need to have a way to invalidate cached versions.

            return cache_filepath

        suffix = filepath.suffix
        if suffix.lower() in (".jpg", ".jpeg"):
            resize_jpeg(filepath, cache_filepath, scaled_min_length)
        elif suffix.lower() == ".gif":
            resize_gif(filepath, cache_filepath, scaled_min_length)
        elif suffix.lower() == ".mp4":
            resize_mp4(filepath, cache_filepath, scaled_min_length)
        else:
            raise RuntimeError(f"filetype with suffix '{suffix}' not supported")

        return cache_filepath
