import logging
from fractions import Fraction
from pathlib import Path

import av
from PIL import Image

logger = logging.getLogger(__name__)


FORMAT_OPTIONS = {
    ".jpg": {"quality": 90, "optimize": True},
    ".gif": {"optimize": True},
    ".webp": {"quality": 90, "method": 0, "lossless": False},
    ".avif": {"quality": 90, "speed": 10, "lossless": False},
}


def __pil_img_save(images: list[Image.Image], file_out: Path, durations: int | list[int] | tuple[int, ...] | None = None):
    try:
        format_params = FORMAT_OPTIONS[file_out.suffix.lower()]
    except KeyError as exc:
        raise RuntimeError(f"Unsupported format: {file_out.suffix}") from exc

    sequence_params = {}
    if len(images) > 1:
        assert durations is not None, "when saving multiple images for an animation, duration per frame needs to be given!"

        # webp, gif and avif have the save_all option for animations, jpeg not.
        sequence_params = {
            "save_all": True,
            "append_images": images[1:] if len(images) > 1 else [],
            "duration": durations,  # config.duration,  # duration per frame in milliseconds. integer=all frames same, list/tuple individual.
            "loop": 0,  # loop forever
        }

    images[0].save(file_out, format=None, **format_params, **sequence_params)


def __pyav_mp4_save(images: list[Image.Image], file_out: Path, duration: int):
    # ref https://github.com/PyAV-Org/PyAV/blob/main/examples/numpy/generate_video_with_pts.py
    fps = round(1.0 / (duration / 1000.0))  # duration is in [ms], normize to [s] for pyav

    in_img_w = images[0].width  # it is safe to assume all images have same dimensions
    in_img_h = images[0].height
    even_w = in_img_w if in_img_w % 2 == 0 else in_img_w - 1
    even_h = in_img_h if in_img_h % 2 == 0 else in_img_h - 1

    # set flag to crop. crop using PIL is more efficient than using reformatter to rescale by 1px.
    need_crop = (even_w, even_h) != (in_img_w, in_img_h)
    if need_crop:
        for i, image in enumerate(images):
            images[i] = image.crop(box=(0, 0, even_w, even_h))

    container = av.open(file_out, mode="w")
    stream = container.add_stream("h264", rate=fps, options={"crf": "20", "preset": "veryfast"})  # crf lower is better quality
    stream.codec_context.time_base = Fraction(1, fps)
    stream.width = even_w
    stream.height = even_h
    # high compat. # TODO: does this automatically reformat if the input is different or just states it should be yuv420?
    stream.pix_fmt = "yuv420p"

    my_pts = 0  # [seconds]
    for image in images:
        frame = av.VideoFrame.from_image(image)
        # frame = frame.reformat(format="yuv420p")# TODO: needed?
        frame.pts = my_pts
        my_pts += 1.0

        for packet in stream.encode(frame):
            container.mux(packet)

    # last frame duplication seems not needed here, it plays correctly without

    # Flush stream
    for packet in stream.encode():
        container.mux(packet)

    # Close the file
    container.close()


def encode(images: list[Image.Image], file_out: Path, durations: int | list[int] | tuple[int, ...] | None = None):
    save_to_format = file_out.suffix.lower()

    if save_to_format in FORMAT_OPTIONS.keys():
        __pil_img_save(images, file_out, durations)
    elif save_to_format == ".mp4":
        if type(durations) is not int:
            raise ValueError("save mp4 needs a fixed duration")
        __pyav_mp4_save(images, file_out, durations)
    else:
        raise RuntimeError(f"format {save_to_format} is not supported!")
