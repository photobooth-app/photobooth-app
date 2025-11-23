import logging
from pathlib import Path

import av
import piexif
from av import VideoStream
from PIL import Image, ImageOps, ImageSequence

logger = logging.getLogger(__name__)
try:
    from turbojpeg import TurboJPEG

    turbojpeg = TurboJPEG()
    print("using turbojpeg to scale images")  # print because log at this point not yet active...
except Exception:
    turbojpeg = None
    print("cannot find turbojpeg lib, falling back to slower pillow scale algorithm. If you want to use turbojpeg install the library.")


def resize_jpeg_pillow(filepath_in: Path, filepath_out: Path, scaled_min_length: int):
    """scale a jpeg buffer to another buffer using pillow"""

    image = Image.open(filepath_in)

    # scale by factor to determine
    original_length = max(image.width, image.height)  # scale for the max length
    scaling_factor = scaled_min_length / original_length

    width = int(image.width * scaling_factor)
    height = int(image.height * scaling_factor)
    dim = (width, height)

    # https://pillow.readthedocs.io/en/latest/handbook/concepts.html#filters-comparison-table
    image.thumbnail(dim, Image.Resampling.BICUBIC)  # bicubic for comparison, does not upscale, which is what we want.

    # transpose the image to the correct orientation (same as piexif transplant the exif data)
    ImageOps.exif_transpose(image, in_place=True)

    # encode to jpeg again
    image.save(filepath_out, quality=85)


def resize_jpeg_turbojpeg(filepath_in: Path, filepath_out: Path, scaled_min_length: int):
    assert turbojpeg is not None

    with open(filepath_in, "rb") as file_in:
        jpeg_bytes_in = file_in.read()

    (width, height, _, _) = turbojpeg.decode_header(jpeg_bytes_in)

    original_length = max(width, height)  # scale for the max length
    scaling_factor = scaled_min_length / original_length

    # TurboJPEG only allows for decent factors.
    factor_list = [item[0] / item[1] for item in turbojpeg.scaling_factors]
    (index, factor) = min(enumerate(factor_list), key=lambda x: abs(x[1] - scaling_factor))

    # logger.debug(f"scaling img by factor {factor}, {original_length=} -> {scaled_min_length=}")
    if factor > 1:
        logger.warning("scale factor bigger than 1 - consider optimize config, usually images shall shrink, resizing skipped")
        buffer_out = jpeg_bytes_in
    else:
        buffer_out = turbojpeg.scale_with_quality(jpeg_bytes_in, scaling_factor=list(turbojpeg.scaling_factors)[index], quality=85)

    with open(filepath_out, "wb") as file_out:
        file_out.write(buffer_out)

    # transplanting the exif data to newly produced output because we use the orientation tag to rotate without encoding.
    # same as pillow exif_transpose
    piexif.insert(piexif.dump(piexif.load(str(filepath_in))), str(filepath_out))


def resize_jpeg(filepath_in: Path, filepath_out: Path, scaled_min_length: int):
    if turbojpeg:
        resize_jpeg_turbojpeg(filepath_in, filepath_out, scaled_min_length)
    else:
        resize_jpeg_pillow(filepath_in, filepath_out, scaled_min_length)


def resize_animation_pillow(filepath_in: Path, filepath_out: Path, scaled_min_length: int):
    """Scale an animated image sequence (GIF/WebP/AVIF) and preserve frame durations."""

    # format specific optimizations:
    FORMAT_OPTIONS = {
        ".gif": {"optimize": True},
        ".webp": {"quality": 85, "method": 0, "lossless": False},
        ".avif": {"quality": 85, "speed": 10, "lossless": False},
    }
    try:
        format_params = FORMAT_OPTIONS[filepath_out.suffix.lower()]
    except KeyError as exc:
        raise RuntimeError(f"Unsupported format: {filepath_out.suffix.lower()}") from exc

    pil_animated_img = Image.open(filepath_in)
    durations: list[int] = []
    resized_frames: list[Image.Image] = []
    for frame in ImageSequence.Iterator(pil_animated_img):
        frame.load()  # ensure metadata is parsed so for AVIF/WEBP duration is avail. GIF is different and would not need this.
        thumb = frame.copy()
        thumb.thumbnail((scaled_min_length, scaled_min_length), Image.Resampling.LANCZOS)
        resized_frames.append(thumb)
        d = frame.info.get("duration", pil_animated_img.info.get("duration", 1000))
        durations.append(int(d))

    # Save output
    resized_frames[0].save(
        filepath_out,
        format=None,
        save_all=True,
        append_images=resized_frames[1:],
        duration=durations,
        loop=0,
        **format_params,
    )


def resize_mp4(filepath_in: Path, filepath_out: Path, scaled_min_length: int):
    def scale_image_to_min_longest_side(width: int, height: int, max_longest_side: int):
        longest_side = max(width, height)

        # Only scale down if it's larger than the max allowed
        if longest_side <= max_longest_side:
            return width, height  # no scaling needed

        scale_factor = max_longest_side / longest_side
        new_width = int(width * scale_factor)
        new_height = int(height * scale_factor)

        new_width += new_width % 2  # round up to nearest even number
        new_height += new_height % 2  # round up to nearest even number

        return new_width, new_height

    input_container = av.open(filepath_in)
    input_stream = input_container.streams.video[0]
    input_stream.thread_type = "AUTO"  # speed up decoding, see benchmark results.
    input_stream.thread_count = 0

    ow, oh = scale_image_to_min_longest_side(input_stream.width, input_stream.height, scaled_min_length)

    output_container = av.open(filepath_out, mode="w")
    output_stream: VideoStream = output_container.add_stream("h264", rate=input_stream.codec_context.framerate)  # rate is fps
    output_stream.width = ow
    output_stream.height = oh
    output_stream.codec_context.options["movflags"] = "faststart"
    output_stream.codec_context.options["preset"] = "veryfast"
    output_stream.codec_context.options["crf"] = "23"  # 23 default, 17-18 is visually lossless
    # output_stream.codec_context.bit_rate = 5000000  # 5000k==5Mbps seems reasonable for simple streams in the 1080range

    for frame in input_container.decode(input_stream):
        # Das Frame in der Zielgröße skalieren
        scaled_frame = frame.reformat(
            width=output_stream.width,
            height=output_stream.height,
            # interpolation=Interpolation.BILINEAR, # default is BILINEAR
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


def resize(filepath_in: Path, filepath_out: Path, scaled_min_length: int) -> None:
    assert isinstance(filepath_in, Path)
    assert isinstance(filepath_out, Path)

    suffix = filepath_in.suffix

    # logger.debug(f"resize {filepath_in} to length {scaled_min_length}, save in {filepath_out}")

    if suffix.lower() in (".jpg", ".jpeg"):
        resize_jpeg(filepath_in, filepath_out, scaled_min_length)
    elif suffix.lower() in (".gif", ".webp", ".avif"):
        resize_animation_pillow(filepath_in, filepath_out, scaled_min_length)
    elif suffix.lower() == ".mp4":
        resize_mp4(filepath_in, filepath_out, scaled_min_length)
    else:
        raise RuntimeError(f"filetype with suffix '{suffix}' not supported")
