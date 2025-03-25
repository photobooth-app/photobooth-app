"""
Testing mediaprocessing singleimages pipeline
"""

import logging
from collections.abc import Generator
from pathlib import Path

import pytest
from PIL import Image
from pydantic_extra_types.color import Color

from photobooth.appconfig import AppConfig
from photobooth.services.config.groups.actions import TextsConfig
from photobooth.services.mediaprocessing.context import ImageContext
from photobooth.services.mediaprocessing.pipeline import Pipeline
from photobooth.services.mediaprocessing.steps.image import (
    FillBackgroundStep,
    ImageFrameStep,
    ImageMountStep,
    PluginFilters,
    PluginFilterStep,
    RemoveChromakeyStep,
    TextStep,
    get_plugin_avail_filters,
    get_plugin_userselectable_filters,
)
from photobooth.utils.exceptions import PipelineError

from ..util import is_same

logger = logging.getLogger(name=None)


@pytest.fixture()
def pil_image() -> Generator[Image.Image, None, None]:
    yield Image.open("src/tests/assets/input.jpg")


## two test methods to check whether pixels are different or same:
# method1: simple but seems to use high cpu and memory. makes RPI3 die
# method2: more efficient, RPI3 can handle.
# Using method2 to compare in tests.


def test_validate_test_method_same():
    img1 = Image.new("RGB", (5, 5), color=None)
    img2 = Image.new("RGB", (5, 5), color=None)
    assert img1 is not img2  # imgs are not same

    # method 1
    assert list(img2.getdata()) == list(img1.getdata())
    # method 2
    assert is_same(img1, img2)


def test_validate_test_method_different():
    img1 = Image.new("RGB", (5, 5), color=None)
    img2 = Image.new("RGB", (5, 5), color="green")
    assert img1 is not img2  # imgs are not same

    # method 1
    assert list(img2.getdata()) != list(img1.getdata())
    # method 2
    assert not is_same(img1, img2)


def test_pilgram_stage_get_filters():
    # in default all filter enabled
    assert get_plugin_avail_filters() == get_plugin_userselectable_filters()


def test_pilgram_stage(pil_image: Image.Image):
    context = ImageContext(pil_image)
    steps = [PluginFilterStep(PluginFilters("FilterPilgram2.aden"))]
    pipeline = Pipeline[ImageContext](*steps)
    pipeline(context)
    stage_output = context.image

    assert pil_image.mode == "RGB"
    assert stage_output.mode == pil_image.mode
    assert pil_image.size == stage_output.size
    assert pil_image is not stage_output  # original is not modified
    assert not is_same(pil_image, stage_output)


def test_pilgram_stage_rgba_kept(pil_image: Image.Image):
    pil_image = pil_image.convert("RGBA")

    context = ImageContext(pil_image)
    steps = [PluginFilterStep(PluginFilters("FilterPilgram2.aden"))]
    pipeline = Pipeline[ImageContext](*steps)
    pipeline(context)
    stage_output = context.image

    assert pil_image.mode == "RGBA"
    assert stage_output.mode == pil_image.mode
    assert pil_image.size == stage_output.size
    assert pil_image is not stage_output  # original is not modified
    assert not is_same(pil_image, stage_output)


def test_pilgram_stage_nonexistantfilter(pil_image: Image.Image):
    with pytest.raises(ValueError):
        # yes right! original is no filter ;)
        context = ImageContext(pil_image)
        steps = [PluginFilterStep(PluginFilters("FilterPilgram2.original"))]
        pipeline = Pipeline[ImageContext](*steps)
        pipeline(context)


def test_text_stage(pil_image: Image.Image):
    textconfig = [TextsConfig(text="apply text", font=Path("userdata/demoassets/fonts/Roboto-Bold.ttf"))]
    context = ImageContext(pil_image)
    steps = [TextStep(textconfig)]
    pipeline = Pipeline[ImageContext](*steps)
    pipeline(context)
    stage_output = context.image

    assert pil_image is not stage_output


def test_text_stage_fontnotavail(pil_image: Image.Image):
    textconfig = [TextsConfig(text="asdf", font=None)]

    with pytest.raises(PipelineError):
        context = ImageContext(pil_image)
        steps = [TextStep(textconfig)]
        pipeline = Pipeline[ImageContext](*steps)
        pipeline(context)


def test_text_stage_empty_emptyarray_skips(pil_image: Image.Image):
    textconfig = []

    context = ImageContext(pil_image)
    steps = [TextStep(textconfig)]
    pipeline = Pipeline[ImageContext](*steps)
    pipeline(context)
    stage_output = context.image

    assert pil_image is not stage_output  # original copied, so not equal
    assert is_same(pil_image, stage_output)  # but pixel are same because empty textconfig


def test_text_stage_empty_emptytext_skips(pil_image: Image.Image):
    textconfig = [TextsConfig(text=""), TextsConfig(pos_x=1), TextsConfig(pos_y=1), TextsConfig(font_size=100)]

    context = ImageContext(pil_image)
    steps = [TextStep(textconfig)]
    pipeline = Pipeline[ImageContext](*steps)
    pipeline(context)
    stage_output = context.image

    assert pil_image is not stage_output  # original copied, so not equal
    assert is_same(pil_image, stage_output)  # but pixel are same because empty textconfig


def test_removechromakey_stage(pil_image: Image.Image):
    keycolor = AppConfig().mediaprocessing.removechromakey_keycolor
    tolerance = AppConfig().mediaprocessing.removechromakey_tolerance

    assert pil_image.mode == "RGB"  # before process it's RGB

    context = ImageContext(pil_image)
    steps = [RemoveChromakeyStep(keycolor, tolerance)]
    pipeline = Pipeline[ImageContext](*steps)
    pipeline(context)
    stage_output = context.image

    assert stage_output.mode == "RGBA"  # after process always RGBA
    assert pil_image is not stage_output  # original copied here, so not equal
    assert is_same(pil_image, stage_output)  # but pixel are same because empty textconfig


def test_fill_background_stage(pil_image: Image.Image):
    pil_image = pil_image.convert("RGBA")
    assert pil_image.mode == "RGBA"  # before process it's RGBA

    # emulate that some parts of the image are transparent - otherwise background cannot shine through and image data equals.
    pil_image.putalpha(100)

    context = ImageContext(pil_image)
    steps = [FillBackgroundStep(Color("yellow"))]
    pipeline = Pipeline[ImageContext](*steps)
    pipeline(context)
    stage_output = context.image

    assert stage_output.mode == "RGBA"  # ensure it keeps RGBA
    assert pil_image is not stage_output  # original is not changed
    assert not is_same(pil_image, stage_output)  # pixel are diff because background shines through


def test_fill_background_stage_notransparency(pil_image: Image.Image):
    pil_image = pil_image.convert("RGBA")
    assert pil_image.mode == "RGBA"  # before process it's RGBA

    context = ImageContext(pil_image)
    steps = [FillBackgroundStep(Color("yellow"))]
    pipeline = Pipeline[ImageContext](*steps)
    pipeline(context)
    stage_output = context.image

    assert stage_output.mode == "RGBA"  # ensure it keeps RGBA
    assert pil_image is not stage_output  # original is not changed
    assert is_same(pil_image, stage_output)  # pixel are still same, because the image had no transparency.


def test_fill_background_stage_accept_str(pil_image: Image.Image):
    pil_image = pil_image.convert("RGBA")
    assert pil_image.mode == "RGBA"  # before process it's RGBA

    # emulate that some parts of the image are transparent - otherwise background cannot shine through and image data equals.
    pil_image.putalpha(100)

    context = ImageContext(pil_image)
    steps = [FillBackgroundStep("yellow")]
    pipeline = Pipeline[ImageContext](*steps)
    pipeline(context)
    stage_output = context.image

    assert stage_output.mode == "RGBA"  # ensure it keeps RGBA
    assert pil_image is not stage_output  # original is not changed
    assert not is_same(pil_image, stage_output)  # pixel are diff because background shines through


def test_img_background_stage(pil_image: Image.Image):
    pil_image = pil_image.convert("RGBA")
    assert pil_image.mode == "RGBA"  # before process it's RGBA

    # emulate that some parts of the image are transparent - otherwise background cannot shine through and image data equals.
    pil_image.putalpha(100)

    context = ImageContext(pil_image)
    steps = [ImageMountStep("./userdata/demoassets/backgrounds/pink-7761356_1920.jpg")]
    pipeline = Pipeline[ImageContext](*steps)
    pipeline(context)
    stage_output = context.image

    assert stage_output.mode == "RGBA"  # ensure it keeps RGBA
    assert pil_image is not stage_output  # original is not changed
    assert not is_same(pil_image, stage_output)  # pixel are diff because background shines through


def test_img_background_stage_rgb_skip_process(pil_image: Image.Image):
    pil_image = pil_image
    assert pil_image.mode == "RGB"  # before process it's RGB

    context = ImageContext(pil_image)
    steps = [ImageMountStep("./userdata/demoassets/backgrounds/pink-7761356_1920.jpg")]
    pipeline = Pipeline[ImageContext](*steps)
    pipeline(context)
    stage_output = context.image

    assert stage_output.mode == "RGB"  # ensure it keeps RGB
    assert pil_image is stage_output  # original is not changed
    assert is_same(pil_image, stage_output)  # pixel are diff because background shines through


def test_img_background_stage_nonexistentfile(pil_image: Image.Image):
    pil_image = pil_image.convert("RGBA")

    with pytest.raises(PipelineError):
        context = ImageContext(pil_image)
        steps = [ImageMountStep("./userdata/demoassets/backgrounds/nonexistentfile")]
        pipeline = Pipeline[ImageContext](*steps)
        pipeline(context)


def test_img_background_stage_reverse(pil_image: Image.Image):
    pil_image = pil_image.convert("RGBA")
    assert pil_image.mode == "RGBA"  # before process it's RGBA

    context = ImageContext(pil_image)
    steps = [ImageMountStep("./src/tests/assets/frames/polaroid-6125402_1pic-transparency.png", reverse=True)]
    pipeline = Pipeline[ImageContext](*steps)
    pipeline(context)
    stage_output = context.image

    assert stage_output.mode == "RGBA"  # ensure it keeps RGBA
    assert pil_image is not stage_output  # original is not changed
    assert not is_same(pil_image, stage_output)  # pixel are diff because background shines through


def test_img_frame_stage(pil_image: Image.Image):
    context = ImageContext(pil_image)
    steps = [ImageFrameStep("./src/tests/assets/frames/polaroid-6125402_1pic-transparency.png")]
    pipeline = Pipeline[ImageContext](*steps)
    pipeline(context)
    stage_output = context.image

    assert stage_output.mode == "RGBA"  # ensure it keeps RGBA
    assert pil_image is not stage_output  # original is not changed
    assert not is_same(pil_image, stage_output)  # pixel are diff because capture is mounted


def test_img_frame_stage_notransparency_rgbamode(pil_image: Image.Image):
    with pytest.raises(PipelineError):
        context = ImageContext(pil_image)
        steps = [ImageFrameStep("./src/tests/assets/frames/polaroid-6125402_1pic-notransparency.png")]
        pipeline = Pipeline[ImageContext](*steps)
        pipeline(context)
        _ = context.image


def test_img_frame_stage_notransparency_rgbmode(pil_image: Image.Image):
    with pytest.raises(PipelineError):
        context = ImageContext(pil_image)
        steps = [ImageFrameStep("./src/tests/assets/frames/polaroid-6125402_1pic.jpg")]
        pipeline = Pipeline[ImageContext](*steps)
        pipeline(context)
        _ = context.image
