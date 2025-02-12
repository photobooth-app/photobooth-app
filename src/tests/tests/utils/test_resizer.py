import logging
from pathlib import Path
from unittest.mock import patch

import pytest
from PIL import Image, ImageOps
from turbojpeg import TurboJPEG

from photobooth.database.types import DimensionTypes
from photobooth.services.collection import MAP_DIMENSION_TO_PIXEL
from photobooth.utils.resizer import generate_resized, resize_gif, resize_jpeg, resize_jpeg_pillow, resize_jpeg_turbojpeg, resize_mp4

from ..util import get_exiforiented_jpeg, get_jpeg

turbojpeg = TurboJPEG()
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
    input = Path("src/tests/assets/animation.gif")
    output = tmp_path / "animation.gif"

    resize_gif(filepath_in=input, filepath_out=output, scaled_min_length=100)

    with Image.open(output) as img:
        img.verify()


def test_resize_mp4(tmp_path):
    input = Path("src/tests/assets/video.mp4")
    output = tmp_path / "video.mp4"

    resize_mp4(filepath_in=input, filepath_out=output, scaled_min_length=100)

    assert output.is_file()


def test_generate_resized():
    import photobooth.utils.resizer

    with patch.object(photobooth.utils.resizer, "resize_jpeg") as mock:
        generate_resized(filepath_in=Path("somefile.jpg"), filepath_out=Path("dontcare"), scaled_min_length=100)

        mock.assert_called_once()

    with patch.object(photobooth.utils.resizer, "resize_jpeg") as mock:
        generate_resized(filepath_in=Path("somefile.jpeg"), filepath_out=Path("dontcare"), scaled_min_length=100)

        mock.assert_called_once()

    with patch.object(photobooth.utils.resizer, "resize_gif") as mock:
        generate_resized(filepath_in=Path("somefile.gif"), filepath_out=Path("dontcare"), scaled_min_length=100)

        mock.assert_called_once()

    with patch.object(photobooth.utils.resizer, "resize_mp4") as mock:
        generate_resized(filepath_in=Path("somefile.mp4"), filepath_out=Path("dontcare"), scaled_min_length=100)

        mock.assert_called_once()


def test_generate_resized_raise_nonavail_format():
    with pytest.raises(RuntimeError):
        generate_resized(filepath_in=Path("somefile.unknownextension"), filepath_out=Path("dontcare"), scaled_min_length=100)


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
