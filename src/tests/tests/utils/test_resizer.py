import importlib
import logging
from pathlib import Path
from unittest.mock import patch

import pytest
from PIL import Image, ImageOps

from photobooth.database.types import DimensionTypes
from photobooth.services.collection import MAP_DIMENSION_TO_PIXEL
from photobooth.utils.media_resizer import (
    resize,
    resize_animation_pillow,
    resize_jpeg,
    resize_jpeg_pillow,
    resize_jpeg_turbojpeg,
    resize_mp4,
)

from ..util import dummy_animation, get_exiforiented_jpeg, get_jpeg

try:
    from turbojpeg import TurboJPEG

    turbojpeg = TurboJPEG()
except Exception:
    pytest.skip("turbojpeg is not avail on this system", allow_module_level=True)

logger = logging.getLogger(name=None)


def test_mapping_avail():
    assert isinstance(MAP_DIMENSION_TO_PIXEL.get(DimensionTypes.full, None), int)
    assert isinstance(MAP_DIMENSION_TO_PIXEL.get(DimensionTypes.preview, None), int)
    assert isinstance(MAP_DIMENSION_TO_PIXEL.get(DimensionTypes.thumbnail, None), int)


def test_resize_jpg(tmp_path):
    input = Path("src/tests/assets/input.jpg")
    output = tmp_path / "output.jpg"

    resize_jpeg(filepath_in=input, filepath_out=output, scaled_min_length=100)

    with Image.open(output) as img:
        img.verify()


def test_resize_jpg_autofallback(tmp_path):
    import turbojpeg

    import photobooth.utils.media_resizer

    with patch.object(turbojpeg, "TurboJPEG", side_effect=ModuleNotFoundError("fake turbojpeg not avail")):
        # need to reload the lib because for the turbojpeg module is checked for availability on import

        importlib.reload(photobooth.utils.media_resizer)

        # ensure turbojpeg has not been loaded
        assert photobooth.utils.media_resizer.turbojpeg is None

        input = Path("src/tests/assets/input.jpg")
        output = tmp_path / "output.jpg"

        resize_jpeg(filepath_in=input, filepath_out=output, scaled_min_length=100)

        # ensure the resized image was generated despite turbojpeg not avail.
        with Image.open(output) as img:
            img.verify()

    # reload again outside of patch to ensure following tests have the turbojpeg available again if needed.
    importlib.reload(photobooth.utils.media_resizer)


def test_resize_jpg_force_turbojpeg(tmp_path):
    input = Path("src/tests/assets/input.jpg")
    output = tmp_path / "output.jpg"

    resize_jpeg_turbojpeg(filepath_in=input, filepath_out=output, scaled_min_length=100)

    with Image.open(output) as img:
        img.verify()


def test_resize_jpg_force_pillow(tmp_path):
    input = Path("src/tests/assets/input.jpg")
    output = tmp_path / "output.jpg"

    resize_jpeg_pillow(filepath_in=input, filepath_out=output, scaled_min_length=100)

    with Image.open(output) as img:
        img.verify()


def test_resize_gif(tmp_path):
    input = tmp_path / "anim.gif"
    output = tmp_path / "animation.gif"
    dummy_animation(input)

    resize_animation_pillow(filepath_in=input, filepath_out=output, scaled_min_length=100)

    with Image.open(output) as img:
        img.verify()


def test_resize_webp(tmp_path):
    input = tmp_path / "anim.webp"
    output = tmp_path / "animation.webp"
    dummy_animation(input)

    resize_animation_pillow(filepath_in=input, filepath_out=output, scaled_min_length=100)

    with Image.open(output) as img:
        img.verify()


def test_resize_avif(tmp_path):
    input = tmp_path / "anim.avif"
    output = tmp_path / "animation.avif"
    dummy_animation(input)

    resize_animation_pillow(filepath_in=input, filepath_out=output, scaled_min_length=100)

    with Image.open(output) as img:
        img.verify()


def test_resize_mp4(tmp_path):
    input = Path("src/tests/assets/video.mp4")
    output = tmp_path / "video.mp4"

    resize_mp4(filepath_in=input, filepath_out=output, scaled_min_length=100)

    assert output.is_file()


def test_generate_resized():
    import photobooth.utils.media_resizer

    with patch.object(photobooth.utils.media_resizer, "resize_jpeg") as mock:
        resize(filepath_in=Path("somefile.jpg"), filepath_out=Path("dontcare"), scaled_min_length=100)
        mock.assert_called_once()

    with patch.object(photobooth.utils.media_resizer, "resize_jpeg") as mock:
        resize(filepath_in=Path("somefile.jpeg"), filepath_out=Path("dontcare"), scaled_min_length=100)
        mock.assert_called_once()

    with patch.object(photobooth.utils.media_resizer, "resize_animation_pillow") as mock:
        resize(filepath_in=Path("somefile.gif"), filepath_out=Path("dontcare"), scaled_min_length=100)
        mock.assert_called_once()

    with patch.object(photobooth.utils.media_resizer, "resize_animation_pillow") as mock:
        resize(filepath_in=Path("somefile.webp"), filepath_out=Path("dontcare"), scaled_min_length=100)
        mock.assert_called_once()

    with patch.object(photobooth.utils.media_resizer, "resize_animation_pillow") as mock:
        resize(filepath_in=Path("somefile.avif"), filepath_out=Path("dontcare"), scaled_min_length=100)
        mock.assert_called_once()

    with patch.object(photobooth.utils.media_resizer, "resize_mp4") as mock:
        resize(filepath_in=Path("somefile.mp4"), filepath_out=Path("dontcare"), scaled_min_length=100)
        mock.assert_called_once()


def test_generate_resized_raise_nonavail_format():
    with pytest.raises(RuntimeError):
        resize(filepath_in=Path("somefile.unknownextension"), filepath_out=Path("dontcare"), scaled_min_length=100)


def test_exif_transpose():
    dim = (100, 50)
    orientation = 5  # 5==90° transpose
    jpeg_bytes_io = get_jpeg(dim)

    updated_jpeg_bytes_io = get_exiforiented_jpeg(jpeg_bytes_io, orientation)

    # orientation 5 check
    assert Image.open(jpeg_bytes_io).size == dim  # no orientation flag here, so same as input.
    assert Image.open(updated_jpeg_bytes_io).size == dim  # dim is not reversed because exif_transpose was not applied

    img_transposed = ImageOps.exif_transpose(Image.open(jpeg_bytes_io))
    assert img_transposed
    assert img_transposed.size == dim  # no orientation flag here, so same as input.
    update_img_transpose = ImageOps.exif_transpose(Image.open(updated_jpeg_bytes_io))
    assert update_img_transpose
    assert update_img_transpose.size == dim[::-1]  # dim reversed because orientation 5=90°
