import logging
from pathlib import Path

import av
import piexif
from PIL import Image, ImageOps, ImageSequence, UnidentifiedImageError
from turbojpeg import TurboJPEG

logger = logging.getLogger(__name__)
try:
    turbojpeg = TurboJPEG()
    print("using turbojpeg to scale images")  # print because log at this point not yet active...
except RuntimeError:
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

    logger.debug(f"scaling img by factor {factor}, {original_length=} -> {scaled_min_length=}")
    if factor > 1:
        logger.warning("scale factor bigger than 1 - consider optimize config, usually images shall shrink")

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


def resize_gif(filepath_in: Path, filepath_out: Path, scaled_min_length: int):
    """scale a gif image sequence to another buffer using PIL"""
    try:
        gif_image = Image.open(filepath_in, formats=["gif"])
    except (UnidentifiedImageError, Exception) as exc:
        logger.error(f"loading gif failed: {exc}")
        raise RuntimeError(f"filetype not supported, error: {exc}") from exc

    # Wrap on-the-fly thumbnail generator
    def thumbnails(frames: ImageSequence.Iterator, target_size: tuple[int, int]):
        for frame in frames:
            thumbnail = frame.copy()
            thumbnail.thumbnail(size=target_size, resample=Image.Resampling.LANCZOS)
            yield thumbnail

    # to recover the original durations in scaled versions
    durations = []
    for frame in ImageSequence.Iterator(gif_image):
        duration = frame.info.get("duration", 1000)  # fallback 1sec if info not avail.
        durations.append(duration)

    # Get sequence iterator
    resized_frames = thumbnails(ImageSequence.Iterator(gif_image), (scaled_min_length, scaled_min_length))

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
    def scale_image_to_min_longest_side(width, height, max_longest_side):
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
    output_stream = output_container.add_stream("h264", rate=input_stream.codec_context.framerate)  # rate is fps
    output_stream.width = ow
    output_stream.height = oh
    output_stream.codec_context.options["movflags"] = "faststart"
    output_stream.codec_context.options["preset"] = "fast"
    output_stream.codec_context.bit_rate = 5000000  # 5000k==5Mbps seems reasonable for simple streams in the 1080range

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


def generate_resized(filepath_in: Path, filepath_out: Path, scaled_min_length: int) -> None:
    assert isinstance(filepath_in, Path)
    assert isinstance(filepath_out, Path)

    suffix = filepath_in.suffix

    logger.debug(f"resize {filepath_in} to length {scaled_min_length}, save in {filepath_out}")

    if suffix.lower() in (".jpg", ".jpeg"):
        resize_jpeg(filepath_in, filepath_out, scaled_min_length)
    elif suffix.lower() == ".gif":
        resize_gif(filepath_in, filepath_out, scaled_min_length)
    elif suffix.lower() == ".mp4":
        resize_mp4(filepath_in, filepath_out, scaled_min_length)
    else:
        raise RuntimeError(f"filetype with suffix '{suffix}' not supported")
