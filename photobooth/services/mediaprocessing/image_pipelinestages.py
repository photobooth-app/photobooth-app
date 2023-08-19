import logging
from pathlib import Path

import pilgram2
from PIL import Image, ImageDraw, ImageFont

from ...appconfig import TextStageConfig
from ...utils.exceptions import PipelineError

logger = logging.getLogger(__name__)
DATA_PATH = "./data/"
PATH_FONTS = "".join([DATA_PATH, "fonts/"])


def pilgram_stage(image: Image, filter: str) -> Image:
    """ """
    logger.info(f"pilgram filter stage {filter} to apply")
    try:
        algofun = getattr(pilgram2, filter)
    except Exception as exc:
        raise PipelineError(f"pilgram filter {filter} does not exist") from exc
    else:
        # apply filter
        image = algofun(image)

    return image


def text_stage(image: Image, textstageconfig: list[TextStageConfig]) -> Image:
    """ """
    logger.info("text stage to apply")

    for textconfig in textstageconfig:
        logger.debug(f"apply text: {textconfig=}")

        font_path = Path(PATH_FONTS, textconfig.font)

        # check font is avail, otherwise send pipelineerror - so we can recover and continue
        if not font_path.is_file():
            raise PipelineError(f"font {str(font_path)} not found")

        img_font = ImageFont.truetype(
            font=str(font_path),
            size=textconfig.font_size,
        )

        img_draw = ImageDraw.Draw(image)
        img_draw.text(
            (textconfig.pos_x, textconfig.pos_y),
            textconfig.text,
            fill=textconfig.color.as_rgb_tuple(),
            font=img_font,
        )

    return image


def beauty_stage(image: Image) -> Image:
    """ """
    raise PipelineError("beauty_stage not implemented yet")


def frame_stage(image: Image) -> Image:
    """ """
    raise PipelineError("beauty_stage not implemented yet")


def rembg_stage(image: Image) -> Image:
    """ """
    raise PipelineError("rembg_stage not implemented yet")  # https://github.com/danielgatis/rembg


def dummy_blackrect_stage(image: Image) -> Image:
    """ """

    overlay = Image.new(mode=image.mode, size=(100, 100), color="black")
    image.paste(overlay, (200, 200))

    return image
