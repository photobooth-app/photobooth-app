import io
import logging
import shutil
import time
from pathlib import Path
from tempfile import NamedTemporaryFile
from uuid import uuid4

import av
import piexif
from PIL import Image, ImageChops

from photobooth import PATH_CAMERA_ORIGINAL, PATH_PROCESSED, PATH_UNPROCESSED
from photobooth.database.models import Mediaitem
from photobooth.database.types import MediaitemTypes
from photobooth.services.backends.abstractbackend import AbstractBackend
from photobooth.utils.helper import filename_str_time

logger = logging.getLogger(name=None)


def block_until_device_is_running(backend: AbstractBackend):
    """Mostly used for testing to ensure the device is up.

    Returns:
        _type_: _description_
    """
    while not backend.is_running():
        logger.debug("wait for startup")
        time.sleep(0.1)


def get_images(backend: AbstractBackend, multicam_is_error: bool = False):
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
    try:
        for path in backend.wait_for_multicam_files():
            with Image.open(path) as img:
                img.verify()
    except Exception as exc:
        if multicam_is_error:
            raise AssertionError(f"backend did not return valid image bytes, {exc}") from exc


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


def video_duration(path: str | Path) -> float:
    with av.open(path) as container:
        dur = container.streams[0].duration
        tb = container.streams[0].time_base
        assert dur, "cannot determine duration (ticks)"
        assert tb, "cannot determine timebase (s/tick)"

        return float(dur * tb)


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


def dummy_mediaitem():
    img = Image.new("RGB", (600, 400), color="grey")
    img_path_original = Path(
        NamedTemporaryFile(
            mode="wb",
            delete=False,
            dir=PATH_CAMERA_ORIGINAL,
            prefix=f"{filename_str_time()}_pytest_dummy_",
            suffix=".jpg",
        ).name  # name from namedtemporaryfile is the whole path.
    )
    # absolute path's dont work for us, make it relative to home.
    img_path_original = img_path_original.relative_to(Path.cwd())

    img.save(img_path_original)
    shutil.copy(img_path_original, PATH_PROCESSED)
    shutil.copy(img_path_original, PATH_UNPROCESSED)

    new_item_instance = Mediaitem(
        job_identifier=uuid4(),
        media_type=MediaitemTypes.image,
        captured_original=img_path_original,
        unprocessed=Path(PATH_UNPROCESSED, img_path_original.name),
        processed=Path(PATH_PROCESSED, img_path_original.name),
        pipeline_config={},
        show_in_gallery=True,
    )

    return new_item_instance


def dummy_animation(filepath: Path):
    # Create two dummy frames (solid colors for simplicity)
    frame1 = Image.new("RGB", (600, 400), color=(255, 0, 0))  # red
    frame2 = Image.new("RGB", (600, 400), color=(0, 255, 0))  # green
    frame3 = Image.new("RGB", (600, 400), color=(0, 0, 255))  # blue

    # Save into a BytesIO buffer as animated WebP

    frame1.save(
        filepath,
        format=None,
        save_all=True,
        append_images=[frame2, frame3],
        duration=[200, 400, 200],  # per-frame duration in ms
        loop=0,  # 0 = infinite loop
    )


def get_impl_func_for_plugin(plugin, hook):
    # FIXME: not sure yet, why patch.object(GpioLights,"sm_on_enter_state") does not assert_called() eval True but is still correctly called...
    # working around currently with this function:
    for hookimpl in hook.get_hookimpls():
        if hookimpl.plugin == plugin:  # Match specific plugin instance
            return hookimpl

    else:
        raise RuntimeError("Plugin's hook implementation was not found!")
