"""
Testing mediaprocessing singleimages pipeline
"""
import logging

import pytest
from PIL import Image
from pydantic_extra_types.color import Color

import photobooth.services.mediaprocessing.image_pipelinestages as image_stages
from photobooth.services.config import AppConfig, appconfig
from photobooth.services.config.groups.mediaprocessing import TextsConfig
from photobooth.utils.exceptions import PipelineError

from .image_utils import is_same


@pytest.fixture(autouse=True)
def run_around_tests():
    appconfig.reset_defaults()

    yield


logger = logging.getLogger(name=None)


@pytest.fixture()
def pil_image() -> Image.Image:
    yield Image.open("tests/assets/input.jpg")


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


def test_pilgram_stage(pil_image: Image.Image):
    stage_output = image_stages.pilgram_stage(pil_image, "aden")

    assert pil_image.mode == "RGB"
    assert stage_output.mode == pil_image.mode
    assert pil_image.size == stage_output.size
    assert pil_image is not stage_output  # original is not modified
    assert not is_same(pil_image, stage_output)


def test_pilgram_stage_rgba_kept(pil_image: Image.Image):
    pil_image = pil_image.convert("RGBA")
    logger.info(pil_image.mode)

    stage_output = image_stages.pilgram_stage(pil_image, "aden")

    assert pil_image.mode == "RGBA"
    assert stage_output.mode == pil_image.mode
    assert pil_image.size == stage_output.size
    assert pil_image is not stage_output  # original is not modified
    assert not is_same(pil_image, stage_output)


def test_pilgram_stage_nonexistantfilter(pil_image: Image.Image):
    with pytest.raises(PipelineError):
        _ = image_stages.pilgram_stage(pil_image, "original")
        # yes right! original is no filter ;)


def test_text_stage(pil_image: Image.Image):
    textconfig = [TextsConfig(text="apply text")]

    stage_output = image_stages.text_stage(pil_image, textconfig)

    assert pil_image is stage_output  # original IS modified


def test_text_stage_fontnotavail(pil_image: Image.Image):
    textconfig = [TextsConfig(text="asdf", font="fontNoFile")]

    with pytest.raises(PipelineError):
        _ = image_stages.text_stage(pil_image, textconfig)


def test_text_stage_empty_emptyarray_skips(pil_image: Image.Image):
    textconfig = []

    stage_output = image_stages.text_stage(pil_image.copy(), textconfig)

    assert pil_image is not stage_output  # original copied here, so not equal
    assert is_same(pil_image, stage_output)  # but pixel are same because empty textconfig


def test_text_stage_empty_emptytext_skips(pil_image: Image.Image):
    textconfig = [TextsConfig(text=""), TextsConfig(pos_x=1), TextsConfig(pos_y=1), TextsConfig(font_size=100)]

    stage_output = image_stages.text_stage(pil_image.copy(), textconfig)

    assert pil_image is not stage_output  # original copied here, so not equal
    assert is_same(pil_image, stage_output)  # but pixel are same because empty textconfig


def test_removechromakey_stage(pil_image: Image.Image):
    keycolor = AppConfig().mediaprocessing.removechromakey_keycolor
    tolerance = AppConfig().mediaprocessing.removechromakey_tolerance

    assert pil_image.mode == "RGB"  # before process it's RGB

    stage_output = image_stages.removechromakey_stage(pil_image, keycolor, tolerance)

    assert stage_output.mode == "RGBA"  # after process always RGBA
    assert pil_image is not stage_output  # original copied here, so not equal
    assert is_same(pil_image, stage_output)  # but pixel are same because empty textconfig


def test_fill_background_stage(pil_image: Image.Image):
    pil_image = pil_image.convert("RGBA")
    assert pil_image.mode == "RGBA"  # before process it's RGBA

    # emulate that some parts of the image are transparent - otherwise background cannot shine through and image data equals.
    pil_image.putalpha(100)

    stage_output = image_stages.image_fill_background_stage(pil_image, Color("yellow"))

    assert stage_output.mode == "RGBA"  # ensure it keeps RGBA
    assert pil_image is not stage_output  # original is not changed
    assert not is_same(pil_image, stage_output)  # pixel are diff because background shines through


def test_fill_background_stage_notransparency(pil_image: Image.Image):
    pil_image = pil_image.convert("RGBA")
    assert pil_image.mode == "RGBA"  # before process it's RGBA

    stage_output = image_stages.image_fill_background_stage(pil_image, Color("yellow"))

    assert stage_output.mode == "RGBA"  # ensure it keeps RGBA
    assert pil_image is not stage_output  # original is not changed
    assert is_same(pil_image, stage_output)  # pixel are still same, because the image had no transparency.


def test_fill_background_stage_accept_str(pil_image: Image.Image):
    pil_image = pil_image.convert("RGBA")
    assert pil_image.mode == "RGBA"  # before process it's RGBA

    # emulate that some parts of the image are transparent - otherwise background cannot shine through and image data equals.
    pil_image.putalpha(100)

    stage_output = image_stages.image_fill_background_stage(pil_image, "yellow")

    assert stage_output.mode == "RGBA"  # ensure it keeps RGBA
    assert pil_image is not stage_output  # original is not changed
    assert not is_same(pil_image, stage_output)  # pixel are diff because background shines through


def test_img_background_stage(pil_image: Image.Image):
    pil_image = pil_image.convert("RGBA")
    assert pil_image.mode == "RGBA"  # before process it's RGBA

    # emulate that some parts of the image are transparent - otherwise background cannot shine through and image data equals.
    pil_image.putalpha(100)

    stage_output = image_stages.image_img_background_stage(pil_image, "./backgrounds/pink-7761356_1920.jpg")

    assert stage_output.mode == "RGBA"  # ensure it keeps RGBA
    assert pil_image is not stage_output  # original is not changed
    assert not is_same(pil_image, stage_output)  # pixel are diff because background shines through


def test_img_background_stage_rgb_skip_process(pil_image: Image.Image):
    pil_image = pil_image
    assert pil_image.mode == "RGB"  # before process it's RGB

    stage_output = image_stages.image_img_background_stage(pil_image, "./backgrounds/pink-7761356_1920.jpg")

    assert stage_output.mode == "RGB"  # ensure it keeps RGBA
    assert pil_image is stage_output  # original is not changed
    assert is_same(pil_image, stage_output)  # pixel are diff because background shines through


def test_img_background_stage_nonexistentfile(pil_image: Image.Image):
    pil_image = pil_image.convert("RGBA")

    with pytest.raises(PipelineError):
        _ = image_stages.image_img_background_stage(pil_image, "./backgrounds/nonexistentfile")


def test_img_background_stage_reverse(pil_image: Image.Image):
    pil_image = pil_image.convert("RGBA")
    assert pil_image.mode == "RGBA"  # before process it's RGBA

    stage_output = image_stages.image_img_background_stage(pil_image, "./frames/polaroid-6125402_1920.png", reverse=True)

    assert stage_output.mode == "RGBA"  # ensure it keeps RGBA
    assert pil_image is not stage_output  # original is not changed
    assert not is_same(pil_image, stage_output)  # pixel are diff because background shines through


def test_img_frame_stage(pil_image: Image.Image):
    stage_output = image_stages.image_frame_stage(pil_image, "./frames/polaroid-6125402_1pic.png")
    # stage_output.show()

    assert stage_output.mode == "RGBA"  # ensure it keeps RGBA
    assert pil_image is not stage_output  # original is not changed
    assert not is_same(pil_image, stage_output)  # pixel are diff because capture is mounted


def test_img_frame_stage_notransparency_rgbamode(pil_image: Image.Image):
    with pytest.raises(PipelineError):
        _ = image_stages.image_frame_stage(pil_image, "./tests/assets/frames/polaroid-6125402_1pic.png")


def test_img_frame_stage_notransparency_rgbmode(pil_image: Image.Image):
    with pytest.raises(PipelineError):
        _ = image_stages.image_frame_stage(pil_image, "./tests/assets/frames/polaroid-6125402_1pic.jpg")


def test_nonexistant_pipelines(pil_image: Image.Image):
    with pytest.raises(PipelineError):
        _ = image_stages.beauty_stage(pil_image)
    with pytest.raises(PipelineError):
        _ = image_stages.rembg_stage(pil_image)
