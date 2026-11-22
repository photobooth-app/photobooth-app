"""
Testing mediaprocessing singleimages pipeline
"""

import logging
from collections.abc import Generator
from pathlib import Path
from typing import Literal

import pytest
from PIL import Image, ImageDraw, ImageOps
from pydantic_extra_types.color import Color

from photobooth.appconfig import AppConfig
from photobooth.database.models import Mediaitem
from photobooth.services.config.groups.actions import CollageProcessing, SingleImageProcessing
from photobooth.services.config.models.models import CollageMergeDefinition, ImageElementConfig, TextElementConfig
from photobooth.services.config.models.watermark import Watermark
from photobooth.services.mediaprocessing.context import ImageContext
from photobooth.services.mediaprocessing.pipeline import Pipeline
from photobooth.services.mediaprocessing.processes import process_and_generate_collage, process_image_inner, process_phase1images
from photobooth.services.mediaprocessing.steps.image import (
    CanvasElementsStep,
    FillBackgroundStep,
    ImageFrameStep,
    ImageMountStep,
    PluginFilters,
    PluginFilterStep,
    RemovebgStep,
    WatermarkStep,
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
    assert list(iter(img2.get_flattened_data())) == list(iter(img1.get_flattened_data()))
    # method 2
    assert is_same(img1, img2)


def test_validate_test_method_different():
    img1 = Image.new("RGB", (5, 5), color=None)
    img2 = Image.new("RGB", (5, 5), color="green")
    assert img1 is not img2  # imgs are not same

    # method 1
    assert list(iter(img2.get_flattened_data())) != list(iter(img1.get_flattened_data()))
    # method 2
    assert not is_same(img1, img2)


def test_pilgram_stage_get_filters():
    # in default all pilgram filter enabled
    def pilgram(filters):
        return [f for f in filters if f[0].startswith("FilterPilgram2.")]

    assert pilgram(get_plugin_avail_filters()) == pilgram(get_plugin_userselectable_filters())


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
    textconfig = [TextElementConfig(text="apply text", font=Path("userdata/demoassets/fonts/Roboto-Bold.ttf"))]
    context = ImageContext(pil_image)
    steps = [CanvasElementsStep(textconfig)]
    pipeline = Pipeline[ImageContext](*steps)
    pipeline(context)
    stage_output = context.image

    assert pil_image is not stage_output


def test_text_stage_fontnotavail(pil_image: Image.Image):
    textconfig = [TextElementConfig(text="asdf", font=None)]

    with pytest.raises(PipelineError):
        context = ImageContext(pil_image)
        steps = [CanvasElementsStep(textconfig)]
        pipeline = Pipeline[ImageContext](*steps)
        pipeline(context)


def test_text_stage_empty_emptyarray_skips(pil_image: Image.Image):
    textconfig = []

    context = ImageContext(pil_image)
    steps = [CanvasElementsStep(textconfig)]
    pipeline = Pipeline[ImageContext](*steps)
    pipeline(context)
    stage_output = context.image

    assert pil_image is not stage_output  # original copied, so not equal
    assert is_same(pil_image, stage_output)  # but pixel are same because empty textconfig


def test_text_stage_empty_emptytext_skips(pil_image: Image.Image):
    textconfig = [TextElementConfig(text=""), TextElementConfig(pos_x=1), TextElementConfig(pos_y=1), TextElementConfig(font_size=100)]

    context = ImageContext(pil_image)
    steps = [CanvasElementsStep(textconfig)]
    pipeline = Pipeline[ImageContext](*steps)
    pipeline(context)
    stage_output = context.image

    assert pil_image is not stage_output  # original copied, so not equal
    assert is_same(pil_image, stage_output)  # but pixel are same because empty textconfig


def test_text_stage_rotates_around_text_center():
    font = Path("userdata/demoassets/fonts/Roboto-Bold.ttf")
    canvas = Image.new("RGB", (800, 800), "white")

    def text_bbox_center(rotate: int) -> tuple[float, float]:
        context = ImageContext(canvas)
        pipeline = Pipeline[ImageContext](CanvasElementsStep([TextElementConfig(text="I", pos_x=600, pos_y=600, rotate=rotate, font=font)]))
        pipeline(context)
        bbox = ImageOps.invert(context.image.convert("L")).getbbox()
        assert bbox
        return ((bbox[0] + bbox[2]) / 2, (bbox[1] + bbox[3]) / 2)

    center_unrotated = text_bbox_center(0)
    center_rotated = text_bbox_center(90)

    # rotation around the canvas center would move the text far away
    assert abs(center_unrotated[0] - center_rotated[0]) <= 3
    assert abs(center_unrotated[1] - center_rotated[1]) <= 3


@pytest.fixture()
def logo_file(tmp_path: Path) -> Path:
    file = tmp_path / "logo.png"
    Image.new("RGBA", (100, 50), (255, 0, 0, 255)).save(file)
    return file


def test_image_element_top_left_and_size(logo_file: Path):
    canvas = Image.new("RGB", (400, 400), "white")
    context = ImageContext(canvas)
    pipeline = Pipeline[ImageContext](
        CanvasElementsStep([ImageElementConfig(type="image", image=logo_file, pos_x=100, pos_y=50, width=100, height=50)])
    )
    pipeline(context)

    assert context.image.mode == "RGB"
    assert context.image.size == canvas.size
    assert context.image.getpixel((100, 50)) == (255, 0, 0)
    assert context.image.getpixel((199, 99)) == (255, 0, 0)
    assert context.image.getpixel((99, 50)) == (255, 255, 255)
    assert context.image.getpixel((200, 99)) == (255, 255, 255)
    assert context.image.getpixel((100, 100)) == (255, 255, 255)


def test_image_element_rotates_around_element_center(logo_file: Path):
    canvas = Image.new("RGBA", (400, 400), (255, 255, 255, 255))
    context = ImageContext(canvas)
    element = ImageElementConfig(type="image", image=logo_file, pos_x=100, pos_y=50, width=100, height=50, rotate=90)
    pipeline = Pipeline[ImageContext](CanvasElementsStep([element]))
    pipeline(context)

    # 100x50 rotated by 90° around center (150, 75) becomes 50x100 spanning x 125..175, y 25..125
    assert context.image.mode == "RGBA"
    assert context.image.getpixel((150, 75)) == (255, 0, 0, 255)
    assert context.image.getpixel((150, 30)) == (255, 0, 0, 255)
    assert context.image.getpixel((110, 75)) == (255, 255, 255, 255)


def test_image_element_opacity_and_order(logo_file: Path):
    canvas = Image.new("RGB", (400, 400), "white")
    context = ImageContext(canvas)
    elements = [
        ImageElementConfig(type="image", image=logo_file, pos_x=0, pos_y=0, width=100, height=50),
        ImageElementConfig(type="image", image=logo_file, pos_x=0, pos_y=0, width=100, height=50, opacity=0.0),
    ]
    pipeline = Pipeline[ImageContext](CanvasElementsStep(elements))
    pipeline(context)

    assert context.image.getpixel((50, 25)) == (255, 0, 0)


def test_image_element_missing_file(logo_file: Path):
    element = ImageElementConfig(type="image", image=logo_file)
    logo_file.unlink()

    with pytest.raises(PipelineError):
        Pipeline[ImageContext](CanvasElementsStep([element]))(ImageContext(Image.new("RGB", (100, 100))))


def test_image_element_no_file():
    with pytest.raises(PipelineError):
        Pipeline[ImageContext](CanvasElementsStep([ImageElementConfig(type="image")]))(ImageContext(Image.new("RGB", (100, 100))))


@pytest.mark.parametrize("fill_method", ["cover", "contain"])
def test_watermark_step_sizes_and_composites(fill_method: Literal["cover", "contain"], tmp_path: Path):
    watermark_file = tmp_path / "watermark.png"
    watermark = Image.new("RGBA", (40, 20), (255, 0, 0, 128))
    ImageDraw.Draw(watermark).rectangle((0, 0, 8, 19), fill=(0, 255, 0, 128))
    ImageDraw.Draw(watermark).rectangle((31, 0, 39, 19), fill=(0, 0, 255, 128))
    watermark.save(watermark_file)
    config = Watermark(enable=True, image=watermark_file, fill_method=fill_method)
    context = ImageContext(Image.new("RGB", (40, 40), (0, 0, 255)))

    Pipeline[ImageContext](WatermarkStep(watermark_file, config.fill_method))(context)

    assert context.image.mode == "RGB"
    assert context.image.size == (40, 40)
    assert context.image.getpixel((20, 20)) == (128, 0, 127)
    if fill_method == "contain":
        assert context.image.getpixel((20, 0)) == (0, 0, 255)
        assert context.image.getpixel((2, 20)) == (0, 128, 127)
    else:
        assert context.image.getpixel((20, 0)) == (128, 0, 127)
        assert context.image.getpixel((2, 20)) == (128, 0, 127)


def test_watermark_step_preserves_alpha(tmp_path: Path):
    watermark_file = tmp_path / "watermark.png"
    watermark = Image.new("RGBA", (2, 1), (255, 0, 0, 128))
    watermark.putpixel((1, 0), (0, 255, 0, 0))
    watermark.save(watermark_file)
    context = ImageContext(Image.new("RGBA", (2, 1), (0, 0, 255, 128)))

    Pipeline[ImageContext](WatermarkStep(watermark_file, "cover"))(context)

    assert context.image.getpixel((0, 0)) == (170, 0, 85, 192)
    assert context.image.getpixel((1, 0)) == (0, 0, 255, 128)


def test_watermark_contain_very_narrow_image(tmp_path: Path):
    watermark_file = tmp_path / "watermark.png"
    Image.new("RGBA", (1, 1000), (255, 0, 0, 255)).save(watermark_file)
    context = ImageContext(Image.new("RGB", (100, 2), "blue"))

    Pipeline[ImageContext](WatermarkStep(watermark_file, "contain"))(context)

    assert context.image.getpixel((49, 0)) == (255, 0, 0)
    assert context.image.getpixel((48, 0)) == (0, 0, 255)


def test_watermark_step_missing_file(tmp_path: Path):
    with pytest.raises(PipelineError, match="not found"):
        Pipeline[ImageContext](WatermarkStep(tmp_path / "missing.png", "cover"))(ImageContext(Image.new("RGB", (2, 2))))


@pytest.mark.parametrize("enabled", [False, True])
def test_watermark_image_pipeline_is_last_and_reprocessable(enabled: bool, tmp_path: Path):
    capture = tmp_path / "capture.png"
    element = tmp_path / "element.png"
    watermark = tmp_path / "watermark.png"
    Image.new("RGB", (8, 8), "blue").save(capture)
    Image.new("RGB", (8, 8), "green").save(element)
    Image.new("RGBA", (8, 8), (255, 0, 0, 128)).save(watermark)
    config = SingleImageProcessing(
        elements_enable=True,
        elements=[ImageElementConfig(type="image", image=element, pos_x=0, pos_y=0, width=8, height=8)],
        watermark=Watermark(enable=enabled, image=watermark),
    )
    config = SingleImageProcessing.model_validate(config.model_dump(mode="json"))

    mediaitem = Mediaitem(processed=tmp_path / "out.jpg", pipeline_config=config.model_dump(mode="json"))

    process_phase1images(capture, mediaitem)

    with Image.open(mediaitem.processed) as result:
        assert result.getpixel((4, 4)) == pytest.approx((128, 64, 0) if enabled else (0, 128, 0), abs=3)
    with Image.open(capture) as original:
        assert original.getpixel((4, 4)) == (0, 0, 255)


@pytest.mark.parametrize("enabled", [False, True])
def test_watermark_collage_pipeline_is_last(enabled: bool, tmp_path: Path):
    capture = tmp_path / "capture.png"
    element = tmp_path / "element.png"
    watermark = tmp_path / "watermark.png"
    Image.new("RGB", (8, 8), "blue").save(capture)
    Image.new("RGB", (8, 8), "green").save(element)
    Image.new("RGBA", (8, 8), (255, 0, 0, 128)).save(watermark)
    config = CollageProcessing(
        canvas_width=8,
        canvas_height=8,
        merge_definition=[CollageMergeDefinition(pos_x=0, pos_y=0, width=8, height=8)],
        canvas_elements_enable=True,
        canvas_elements=[ImageElementConfig(type="image", image=element, pos_x=0, pos_y=0, width=8, height=8)],
        watermark=Watermark(enable=enabled, image=watermark),
    )
    mediaitem = Mediaitem(processed=tmp_path / "out.jpg", pipeline_config=config.model_dump(mode="json"))

    process_and_generate_collage([capture], mediaitem)

    with Image.open(mediaitem.processed) as result:
        assert result.getpixel((4, 4)) == pytest.approx((128, 64, 0) if enabled else (0, 128, 0), abs=3)
    with Image.open(capture) as original:
        assert original.getpixel((4, 4)) == (0, 0, 255)


def test_watermark_enabled_without_image_fails(tmp_path: Path):
    capture = tmp_path / "capture.png"
    Image.new("RGB", (8, 8)).save(capture)
    with pytest.raises(ValueError, match="watermark enabled, but no file"):
        process_image_inner(capture, SingleImageProcessing(watermark=Watermark(enable=True)), preview=False)

    config = CollageProcessing(merge_definition=[], watermark=Watermark(enable=True))
    mediaitem = Mediaitem(processed=tmp_path / "out.jpg", pipeline_config=config.model_dump(mode="json"))
    with pytest.raises(ValueError, match="watermark enabled, but no file"):
        process_and_generate_collage([], mediaitem)


def test_rembg_ai_stage(pil_image: Image.Image):
    ai_model = AppConfig().mediaprocessing.remove_background_model

    assert pil_image.mode == "RGB"  # before process it's RGB

    context = ImageContext(pil_image)
    steps = [RemovebgStep(ai_model)]
    pipeline = Pipeline[ImageContext](*steps)
    pipeline(context)
    stage_output = context.image

    assert stage_output.mode == "RGBA"  # after process always RGBA
    assert pil_image is not stage_output  # original copied here, so not equal


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
    steps = [ImageMountStep("./userdata/demoassets/backgrounds/background.jpg")]
    pipeline = Pipeline[ImageContext](*steps)
    pipeline(context)
    stage_output = context.image

    assert stage_output.mode == "RGBA"  # ensure it keeps RGBA
    assert pil_image is not stage_output  # original is not changed
    assert not is_same(pil_image, stage_output)  # pixel are diff because background shines through


def test_img_background_stage_rgb_skip_process(pil_image: Image.Image):
    assert pil_image.mode == "RGB"  # before process it's RGB

    context = ImageContext(pil_image)
    steps = [ImageMountStep("./userdata/demoassets/backgrounds/background.jpg")]
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


def test_img_background_stage_reverse(pil_image: Image.Image, tmp_path: Path):
    temp_file = tmp_path / "test_image.png"
    # Create an RGBA image with a solid background
    img = Image.new("RGBA", (512, 512), (255, 0, 0, 255))

    # Draw a transparent rectangle directly
    ImageDraw.Draw(img).rectangle((80, 60, 320, 240), fill=(0, 0, 0, 255))
    img.save(temp_file)

    pil_image = pil_image.convert("RGBA")
    assert pil_image.mode == "RGBA"  # before process it's RGBA

    context = ImageContext(pil_image)
    steps = [ImageMountStep(temp_file, reverse=True)]
    pipeline = Pipeline[ImageContext](*steps)
    pipeline(context)
    stage_output = context.image

    assert stage_output.mode == "RGBA"  # ensure it keeps RGBA
    assert pil_image is not stage_output  # original is not changed
    assert not is_same(pil_image, stage_output)  # pixel are diff because background shines through


def test_img_frame_stage(pil_image: Image.Image, tmp_path: Path):
    temp_file = tmp_path / "test_image.png"

    # Create an RGBA image with a solid background
    img = Image.new("RGBA", (512, 512), (255, 0, 0, 255))

    # Draw a transparent rectangle directly
    ImageDraw.Draw(img).rectangle((80, 60, 320, 240), fill=(0, 0, 0, 0))
    img.save(temp_file)

    context = ImageContext(pil_image)
    steps = [ImageFrameStep(temp_file)]
    pipeline = Pipeline[ImageContext](*steps)
    pipeline(context)
    stage_output = context.image

    assert stage_output.mode == "RGBA"  # ensure it keeps RGBA
    assert pil_image is not stage_output  # original is not changed
    assert not is_same(pil_image, stage_output)  # pixel are diff because capture is mounted


def test_img_frame_stage_notransparency_rgbamode(pil_image: Image.Image, tmp_path: Path):
    temp_file = tmp_path / "test_image.png"
    img_solid = Image.new("RGBA", (512, 512), "red")
    img_solid.save(temp_file)

    with pytest.raises(PipelineError):
        context = ImageContext(pil_image)
        steps = [ImageFrameStep(temp_file)]
        pipeline = Pipeline[ImageContext](*steps)
        pipeline(context)
        _ = context.image


def test_img_frame_stage_notransparency_rgbmode(pil_image: Image.Image, tmp_path: Path):
    temp_file = tmp_path / "test_image.jpg"
    img_solid = Image.new("RGB", (512, 512), "red")
    img_solid.save(temp_file)

    with pytest.raises(PipelineError):
        context = ImageContext(pil_image)
        steps = [ImageFrameStep(temp_file)]
        pipeline = Pipeline[ImageContext](*steps)
        pipeline(context)
        _ = context.image
