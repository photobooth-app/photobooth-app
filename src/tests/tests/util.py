import io
import logging
import subprocess
from pathlib import Path

import piexif
from PIL import Image, ImageChops

from photobooth.services.backends.abstractbackend import AbstractBackend

logger = logging.getLogger(name=None)


def get_images(backend: AbstractBackend):
    # logger.info(f"testing backend {backend.__module__}")
    # backend.start()

    try:
        with Image.open(backend.wait_for_still_file()) as img:
            img.verify()
    except Exception as exc:
        raise AssertionError(f"backend did not return valid image bytes, {exc}") from exc

    try:
        with Image.open(io.BytesIO(backend.wait_for_lores_image())) as img:
            img.verify()
    except Exception as exc:
        raise AssertionError(f"backend did not return valid image bytes, {exc}") from exc

    # stop backend, ensure process is joined properly to collect coverage:
    # https://pytest-cov.readthedocs.io/en/latest/subprocess-support.html#if-you-use-multiprocessing-process
    # backend.stop()


def is_same(img1: Image.Image, img2: Image.Image):
    # ensure rgb for both before compare, kind of ignore transparency.
    img1 = img1.convert("RGB")
    img2 = img2.convert("RGB")

    # img1.show()
    # img2.show()

    diff = ImageChops.difference(img2, img1)
    logger.info(diff.getbbox())

    # getbbox returns None if all same, otherwise anything that is evalued to false
    return not bool(diff.getbbox())


def video_duration(input_video: Path | str):
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "csv=p=0",
            str(input_video),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )

    return float(result.stdout)


def video_frames(input_video):
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-count_frames",
            "-show_entries",
            "stream=nb_read_frames",
            "-of",
            "csv=p=0",
            input_video,
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )

    return int(result.stdout)


def get_exiforiented_jpeg(jpeg_bytes_io: io.BytesIO, orientation: int) -> io.BytesIO:
    exif_dict = {"0th": {piexif.ImageIFD.Orientation: orientation}}
    exif_bytes = piexif.dump(exif_dict)

    out_jpeg_bytes_io = io.BytesIO()
    piexif.insert(exif_bytes, jpeg_bytes_io.getvalue(), out_jpeg_bytes_io)

    return out_jpeg_bytes_io


def get_jpeg(dim: tuple[int, int]) -> io.BytesIO:
    im = Image.new("L", dim, "red")
    jpeg_bytes_io = io.BytesIO()
    im.save(jpeg_bytes_io, "jpeg")
    return jpeg_bytes_io


def get_impl_func_for_plugin(plugin, hook):
    # FIXME: not sure yet, why patch.object(GpioLights,"sm_on_enter_state") does not assert_called() eval True but is still correctly called...
    # working around currently with this function:
    for hookimpl in hook.get_hookimpls():
        if hookimpl.plugin == plugin:  # Match specific plugin instance
            return hookimpl

    else:
        raise RuntimeError("Plugin's hook implementation was not found!")
