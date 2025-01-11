import logging
from pathlib import Path
from unittest.mock import patch

import pytest
from PIL import Image

from photobooth.database.types import DimensionTypes
from photobooth.services.mediacollection.resizer import MAP_DIMENSION_TO_PIXEL, generate_resized, resize_gif, resize_jpeg, resize_mp4

logger = logging.getLogger(name=None)


def test_mapping_avail():
    assert isinstance(MAP_DIMENSION_TO_PIXEL.get(DimensionTypes.full, None), int)
    assert isinstance(MAP_DIMENSION_TO_PIXEL.get(DimensionTypes.preview, None), int)
    assert isinstance(MAP_DIMENSION_TO_PIXEL.get(DimensionTypes.thumbnail, None), int)


def test_resize_jpg(tmp_path):
    input = Path("tests/assets/input.jpg")
    output = tmp_path / "output.jpg"

    resize_jpeg(filepath_in=input, filepath_out=output, scaled_min_length=100)

    with Image.open(output) as img:
        img.verify()


def test_resize_gif(tmp_path):
    input = Path("tests/assets/animation.gif")
    output = tmp_path / "animation.gif"

    resize_gif(filepath_in=input, filepath_out=output, scaled_min_length=100)

    with Image.open(output) as img:
        img.verify()


def test_resize_mp4(tmp_path):
    input = Path("tests/assets/video.mp4")
    output = tmp_path / "video.mp4"

    resize_mp4(filepath_in=input, filepath_out=output, scaled_min_length=100)

    assert output.is_file()


def test_generate_resized():
    import photobooth.services.mediacollection.resizer

    with patch.object(photobooth.services.mediacollection.resizer, "resize_jpeg"):
        generate_resized(filepath_in=Path("somefile.jpg"), filepath_out=Path("dontcare"), scaled_min_length=100)

        photobooth.services.mediacollection.resizer.resize_jpeg.assert_called_once()

    with patch.object(photobooth.services.mediacollection.resizer, "resize_jpeg"):
        generate_resized(filepath_in=Path("somefile.jpeg"), filepath_out=Path("dontcare"), scaled_min_length=100)

        photobooth.services.mediacollection.resizer.resize_jpeg.assert_called_once()

    with patch.object(photobooth.services.mediacollection.resizer, "resize_gif"):
        generate_resized(filepath_in=Path("somefile.gif"), filepath_out=Path("dontcare"), scaled_min_length=100)

        photobooth.services.mediacollection.resizer.resize_gif.assert_called_once()

    with patch.object(photobooth.services.mediacollection.resizer, "resize_mp4"):
        generate_resized(filepath_in=Path("somefile.mp4"), filepath_out=Path("dontcare"), scaled_min_length=100)

        photobooth.services.mediacollection.resizer.resize_mp4.assert_called_once()


def test_generate_resized_raise_nonavail_format():
    with pytest.raises(RuntimeError):
        generate_resized(filepath_in=Path("somefile.unknownextension"), filepath_out=Path("dontcare"), scaled_min_length=100)
