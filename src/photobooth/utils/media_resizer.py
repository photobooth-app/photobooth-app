import logging
from pathlib import Path

import av
import av.codec.context
import piexif
from av import VideoStream
from PIL import Image, ImageOps, ImageSequence
from simplejpeg import decode_jpeg, decode_jpeg_header, encode_jpeg
from typing_extensions import deprecated

logger = logging.getLogger(__name__)


@deprecated("use resize_jpeg_simplejpeg")
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


def resize_jpeg_simplejpeg(filepath_in: Path, filepath_out: Path, scaled_min_length: int):

    with open(filepath_in, "rb") as file_in:
        jpeg_bytes_in = file_in.read()

    height, width, _, _ = decode_jpeg_header(jpeg_bytes_in)
    original_length = max(width, height)  # scale for the max length
    scaling_factor = scaled_min_length / original_length

    # simplejpeg will pick the closest fast scaling factor (1/2, 1/4, 1/8)
    target_height = int(height * scaling_factor)
    target_width = int(width * scaling_factor)

    if scaling_factor > 1:
        buffer_out = jpeg_bytes_in
    else:
        decoded_img = decode_jpeg(jpeg_bytes_in, min_height=target_height, min_width=target_width, fastdct=True)
        buffer_out = encode_jpeg(decoded_img, quality=85, fastdct=True)

    with open(filepath_out, "wb") as file_out:
        file_out.write(buffer_out)

    # transplanting the exif data to newly produced output because we use the orientation tag to rotate without encoding.
    # same as pillow exif_transpose
    piexif.insert(piexif.dump(piexif.load(str(filepath_in))), str(filepath_out))


def resize_jpeg(filepath_in: Path, filepath_out: Path, scaled_min_length: int):
    resize_jpeg_simplejpeg(filepath_in, filepath_out, scaled_min_length)  # faster


def resize_webp_avif_gif_pillow(filepath_in: Path, filepath_out: Path, scaled_min_length: int):
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
        thumb.thumbnail((scaled_min_length, scaled_min_length), Image.Resampling.BICUBIC)
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


def resize_gif_pyav(filepath_in: Path, filepath_out: Path, scaled_min_length: int):
    with av.open(filepath_in) as container_in, av.open(filepath_out, mode="w") as container_out:
        stream_in = container_in.streams.video[0]
        tb_in = stream_in.time_base  # GIF timebase (usually 1/100)
        assert tb_in

        # --- Determine output size from first frame
        first_frame = next(container_in.decode(stream_in))
        w, h = first_frame.width, first_frame.height

        scale = scaled_min_length / max(w, h)
        if scale < 1.0:
            new_w = int(w * scale)
            new_h = int(h * scale)
        else:
            new_w, new_h = w, h

        # Rewind
        container_in.seek(0)

        # --- OUTPUT ---
        stream_out = container_out.add_stream("gif", rate=25)
        stream_out.time_base = tb_in
        stream_out.codec_context.time_base = tb_in
        stream_out.width = new_w
        stream_out.height = new_h
        stream_out.pix_fmt = "rgb8"

        last_pts = 0
        rescaled = None

        # --- STREAMING DECODE → RESCALE → ENCODE ---
        for frame in container_in.decode(stream_in):
            assert frame.pts is not None
            last_pts = frame.pts + frame.duration

            # Rescale + convert to rgb8 using libswscale
            rescaled = frame.reformat(width=new_w, height=new_h, format="rgb8", interpolation="BICUBIC")

            for packet in stream_out.encode(rescaled):
                container_out.mux(packet)

        # --- Duplicate last frame ---
        if rescaled is not None:
            # dup = rescaled
            rescaled.pts = last_pts
            for packet in stream_out.encode(rescaled):
                container_out.mux(packet)

        # --- Flush ---
        for packet in stream_out.encode():
            container_out.mux(packet)


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

    with av.open(filepath_in) as input, av.open(filepath_out, mode="w", options={"movflags": "faststart"}) as output:
        in_stream = input.streams.video[0]

        in_stream.thread_type = av.codec.context.ThreadType.AUTO  # speed up decoding, see benchmark results.
        in_stream.thread_count = 0
        in_fps = in_stream.codec_context.framerate  # or input_stream.average_rate?
        in_time_base = in_stream.time_base
        assert in_time_base, "cannot determine timebase of input stream"

        ow, oh = scale_image_to_min_longest_side(in_stream.width, in_stream.height, scaled_min_length)
        out_stream: VideoStream = output.add_stream("h264", rate=in_fps)  # rate is fps
        out_stream.thread_type = av.codec.context.ThreadType.AUTO  # speed up encoding
        out_stream.thread_count = 0
        out_stream.width = ow
        out_stream.height = oh
        out_stream.time_base = in_time_base
        out_stream.codec_context.time_base = in_time_base  # Critical to sync timebase for stream/codec!
        out_stream.codec_context.options["preset"] = "veryfast"
        out_stream.codec_context.options["crf"] = "23"  # 23 default, 17-18 is visually lossless
        # output_stream.codec_context.bit_rate = 5000000  # 5000k==5Mbps seems reasonable for simple streams in the 1080range

        for frame in input.decode(in_stream):
            # Das Frame in der Zielgröße skalieren
            scaled_frame = frame.reformat(
                width=out_stream.width,
                height=out_stream.height,
                # interpolation=Interpolation.BILINEAR, # default is BILINEAR
            )

            # Das skalierte Frame in den Ausgabestream codieren
            for packet in out_stream.encode(scaled_frame):
                output.mux(packet)

        # Restliche Frames flushen
        for packet in out_stream.encode():
            output.mux(packet)


def resize(filepath_in: Path, filepath_out: Path, scaled_min_length: int) -> None:
    assert isinstance(filepath_in, Path)
    assert isinstance(filepath_out, Path)

    suffix = filepath_in.suffix

    # logger.debug(f"resize {filepath_in} to length {scaled_min_length}, save in {filepath_out}")

    if suffix.lower() in (".jpg", ".jpeg"):
        resize_jpeg(filepath_in, filepath_out, scaled_min_length)
    elif suffix.lower() == ".gif":
        resize_gif_pyav(filepath_in, filepath_out, scaled_min_length)
        # could be done by pillow also, but pillow is very slow at it, so we use pyav.
    elif suffix.lower() == ".mp4":
        resize_mp4(filepath_in, filepath_out, scaled_min_length)
    elif suffix.lower() in (".webp", ".avif"):
        resize_webp_avif_gif_pillow(filepath_in, filepath_out, scaled_min_length)
    else:
        raise RuntimeError(f"filetype with suffix '{suffix}' not supported")
