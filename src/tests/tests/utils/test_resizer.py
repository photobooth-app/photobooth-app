import logging
from pathlib import Path
from unittest.mock import patch

import pytest
from PIL import Image, ImageOps

from photobooth.utils.media_resizer import resize, resize_animation_pillow, resize_jpeg, resize_jpeg_pillow, resize_jpeg_simplejpeg, resize_mp4

from ..util import dummy_animation, get_exiforiented_jpeg, get_jpeg

try:
    from turbojpeg import TurboJPEG

    turbojpeg = TurboJPEG()
except Exception:
    pytest.skip("turbojpeg is not avail on this system", allow_module_level=True)

logger = logging.getLogger(name=None)


def test_resize_jpg(tmp_path):
    input = Path("src/tests/assets/input.jpg")
    output = tmp_path / "output.jpg"

    resize_jpeg(filepath_in=input, filepath_out=output, scaled_min_length=100)

    with Image.open(output) as img:
        img.verify()


def test_resize_jpg_force_simplejpeg(tmp_path):
    input = Path("src/tests/assets/input.jpg")
    output = tmp_path / "output.jpg"

    resize_jpeg_simplejpeg(filepath_in=input, filepath_out=output, scaled_min_length=100)

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
    img = Image.open(jpeg_bytes_io)
    assert img.size == dim  # no orientation flag here, so same as input.
    updated_img = Image.open(updated_jpeg_bytes_io)
    assert updated_img.size == dim  # dim is not reversed because exif_transpose was not applied

    img_transposed = ImageOps.exif_transpose(Image.open(jpeg_bytes_io))
    assert img_transposed is not None
    assert img_transposed.size == dim  # no orientation flag here, so same as input.
    update_img_transpose = ImageOps.exif_transpose(Image.open(updated_jpeg_bytes_io))
    assert update_img_transpose
    assert update_img_transpose.size == dim[::-1]  # dim reversed because orientation 5=90°
