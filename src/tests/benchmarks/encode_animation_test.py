import io
import logging
from collections.abc import Generator
from typing import Any

import pytest
from PIL import Image

logger = logging.getLogger(name=None)


@pytest.fixture
def dummy_images() -> Generator[list[Image.Image], Any, None]:
    yield [
        Image.open("src/tests/assets/input_lores.jpg"),
        Image.open("src/tests/assets/input_lores.jpg").rotate(180),
        Image.open("src/tests/assets/input_lores.jpg"),
        Image.open("src/tests/assets/input_lores.jpg").rotate(180),
        Image.open("src/tests/assets/input_lores.jpg"),
        Image.open("src/tests/assets/input_lores.jpg").rotate(180),
    ]


def pillow_encode_gif(images: list[Image.Image]):
    byte_io = io.BytesIO()
    ## create mediaitem
    images[0].save(
        byte_io,
        format="gif",
        save_all=True,
        append_images=images[1:] if len(images) > 1 else [],
        optimize=True,
        # duration per frame in milliseconds. integer=all frames same, list/tuple individual.
        duration=125,
        loop=0,  # loop forever
    )

    bytes_full = byte_io.getbuffer()
    # Path("file.gif").write_bytes(bytes_full)
    return bytes_full


def pillow_encode_webp(images: list[Image.Image]):
    byte_io = io.BytesIO()
    ## create mediaitem
    images[0].save(
        byte_io,
        format="WebP",
        save_all=True,
        append_images=images[1:] if len(images) > 1 else [],
        quality=85,
        method=0,
        lossless=False,
        duration=125,
        loop=0,  # loop forever
    )

    bytes_full = byte_io.getbuffer()
    # Path("file.webp").write_bytes(bytes_full)
    return bytes_full


@pytest.fixture(
    params=[
        "pillow_encode_gif",
        "pillow_encode_webp",
    ]
)
def library(request):
    yield request.param


# needs pip install pytest-benchmark
@pytest.mark.benchmark(group="encode_animation")
def test_libraries_encode_hires(library, dummy_images, benchmark):
    benchmark(eval(library), images=dummy_images)
    assert True
