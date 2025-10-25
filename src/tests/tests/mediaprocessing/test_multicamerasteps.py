import logging
from collections.abc import Generator
from pathlib import Path
from typing import Any

import pytest
from PIL import Image, ImageDraw

from photobooth.services.mediaprocessing.context import MulticameraContext
from photobooth.services.mediaprocessing.pipeline import Pipeline
from photobooth.services.mediaprocessing.steps.multicamera import AutoPivotPointStep, CropCommonAreaStep, OffsetPerOpticalFlowStep

logger = logging.getLogger(name=None)


def dummy_image(size: tuple[int, int] = (400, 250), offset_x: int = 0, offset_y: int = 0) -> Image.Image:
    elli_rad = 5
    mask = Image.new("L", size, 0)
    draw = ImageDraw.Draw(mask)
    draw.rectangle((0, 0, elli_rad, elli_rad), fill=255)

    canvas = Image.new("RGB", size, "green")

    center_x = int(round(size[0] / 2 + offset_x - elli_rad / 2))
    center_y = int(round(size[1] / 2 + offset_y - elli_rad / 2))
    canvas.paste(mask, (center_x, center_y), mask=mask)

    return canvas


@pytest.fixture
def dummy_images() -> Generator[list[Image.Image], Any, None]:
    yield [
        dummy_image(offset_x=0, offset_y=0),
        dummy_image(offset_y=10),
        dummy_image(offset_x=15),
        dummy_image(offset_x=-10, offset_y=-20),
        dummy_image(offset_y=-10),
        dummy_image(offset_x=-10),
        dummy_image(offset_x=-10, offset_y=-20),
        dummy_image(offset_x=20, offset_y=10),
        dummy_image(offset_x=-10, offset_y=20),
        dummy_image(offset_y=-10),
        dummy_image(offset_x=10, offset_y=-20),
    ]


def test_pipeline_multicamera(dummy_images: list[Image.Image], tmp_path: Path):
    for num, img in enumerate(dummy_images):
        img.save(f"tmp/input_{num}.jpg")

    context = MulticameraContext(dummy_images)
    steps = []
    steps.append(AutoPivotPointStep())
    steps.append(OffsetPerOpticalFlowStep())
    steps.append(CropCommonAreaStep())

    pipeline = Pipeline[MulticameraContext](*steps)
    pipeline(context)

    # sequence like 1-2-3-4-3-2-restart
    sequence_images = context.images
    sequence_images = sequence_images + list(reversed(sequence_images[1 : len(sequence_images) - 1]))  # add reversed list except first+last item

    ## create mediaitem
    sequence_images[0].save(
        tmp_path / "wigglecam.gif",
        format="gif",
        save_all=True,
        append_images=sequence_images[1:] if len(sequence_images) > 1 else [],
        optimize=True,
        # duration per frame in milliseconds. integer=all frames same, list/tuple individual.
        duration=125,
        loop=0,  # loop forever
    )
    # assert False
