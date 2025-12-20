from __future__ import annotations

import hashlib
import logging
import time
from collections import OrderedDict
from datetime import datetime
from enum import Enum
from itertools import chain
from pathlib import Path
from threading import Lock

from PIL import Image, ImageDraw, ImageFont, ImageOps
from pydantic_extra_types.color import Color

from ....plugins import pm
from ....utils.exceptions import PipelineError
from ....utils.rembg.rembg import remove
from ....utils.rembg.session_factory import new_session
from ....utils.rembg.sessions.base import BaseSession
from ...config.groups.mediaprocessing import RembgModelType
from ...config.models import models
from ..context import ImageContext
from ..pipeline import NextStep, PipelineStep

logger = logging.getLogger(__name__)

rembg_session: BaseSession | None = None
REMOVE_CACHE: OrderedDict[str, Image.Image] = OrderedDict()
MAX_CACHE = 3
LOCK_CACHE = Lock()


def get_plugin_avail_filters():
    return (("original", "original"),) + tuple(((f, f"{f}")) for f in chain(*pm.hook.mp_avail_filter()))


def get_plugin_userselectable_filters():
    return (("original", "original"),) + tuple(((f, f"{f}")) for f in chain(*pm.hook.mp_userselectable_filter()))


PluginFilters = Enum("PluginFilters", get_plugin_avail_filters(), type=str)


class PluginFilterStep(PipelineStep):
    def __init__(self, plugin_filter: PluginFilters) -> None:
        self.plugin_filter: PluginFilters = plugin_filter

    def __call__(self, context: ImageContext, next_step: NextStep) -> None:
        if (not self.plugin_filter) or (self.plugin_filter and self.plugin_filter.value == "original"):
            # nothing to do here...
            next_step(context)
            return  # needed, otherwise remaining code will be executed after returning from next_step

        try:
            manipulated_image = pm.hook.mp_filter_pipeline_step(
                image=context.image.copy(),
                plugin_filter=self.plugin_filter.value,
                preview=context.preview,
            )
        except Exception as exc:
            raise PipelineError(f"plugin filter error: {exc}") from exc

        assert isinstance(manipulated_image, Image.Image), "plugin filter result is wrong type!"

        context.image = manipulated_image

        next_step(context)


class FillBackgroundStep(PipelineStep):
    def __init__(self, color: Color | str) -> None:
        self.color = color

    def __call__(self, context: ImageContext, next_step: NextStep) -> None:
        if not context.image.has_transparency_data:
            logger.warning("no transparency in image, fill background skipped!")
            next_step(context)
            return  # needed, otherwise remaining code will be executed after returning from next_step

        # force color to be of type color again, might be bug in pydantic.
        bg_filled_img = Image.new(mode=context.image.mode, size=context.image.size, color=Color(self.color).as_rgb_tuple())
        bg_filled_img.paste(context.image, mask=context.image)

        context.image = bg_filled_img
        bg_filled_img = None

        next_step(context)


class ImageMountStep(PipelineStep):
    def __init__(self, background_file: Path | str, reverse: bool = False) -> None:
        self.background_file = background_file
        self.reverse = reverse

    def __call__(self, context: ImageContext, next_step: NextStep) -> None:
        if not context.image.has_transparency_data:
            logger.warning("no transparency in image, fill background skipped!")
            next_step(context)
            return  # needed, otherwise remaining code will be executed after returning from next_step

        try:
            background_path = self.background_file
            background_img = Image.open(background_path).convert("RGBA")
        except FileNotFoundError as exc:
            raise PipelineError(f"file {str(self.background_file)} not found!") from exc

        # fit background image to actual image size
        # this might crop the background but fills the image fully. automatic centered.
        background_img_adjusted = ImageOps.fit(
            background_img,
            context.image.size,
            method=Image.Resampling.LANCZOS,
        )

        # paste the actual image to the background
        if self.reverse:
            # copy() to output a new image so return output is consistent between reverse True/False
            output = context.image.copy()
            # mount loaded file on top of image.
            output.paste(background_img_adjusted, mask=background_img_adjusted)
            context.image = output
        else:
            # mount image on top of loaded file.
            background_img_adjusted.paste(context.image, mask=context.image)
            context.image = background_img_adjusted

        next_step(context)


class ImageFrameStep(PipelineStep):
    """optimized function for use on single images.
    resulting size is derived from the frame, since frame is considered as the "master"
    detects transparent area in frame and fits captured image best as possible
    using fit-cover strategy. means captured image can loose some parts if
    aspect ratio of transparent area and captured image are not equal"""

    def __init__(self, frame_file: Path | str) -> None:
        self.frame_file = frame_file

    def __call__(self, context: ImageContext, next_step: NextStep) -> None:
        # check frame is avail, otherwise send pipelineerror
        try:
            frame_path = self.frame_file
            # convert to rgba because there could be paletted PNGs in mode P but still with alpha in info.transparency.
            # converting to RGBA moves info.transparency to actual channel and handling is easy
            image_frame = Image.open(frame_path).convert("RGBA")
        except FileNotFoundError as exc:
            raise PipelineError(f"file {str(self.frame_file)} not found!") from exc

        try:
            # detect boundary box of transparent area, for this get alphachannel, invert and getbbox:
            transparent_xy = ImageOps.invert(image_frame.getchannel("A")).getbbox()  # getchannel A returns img mode 'L'
        except Exception as exc:  # no transparent channel A
            raise PipelineError(f"error processing image, cannot apply stage, error {exc}") from exc

        if transparent_xy is None:
            raise PipelineError("image has alphachannel but actually has not transparent area, cannot apply stage")

        transparent_size = (transparent_xy[2] - transparent_xy[0], transparent_xy[3] - transparent_xy[1])

        logger.info(f"detected transparent area {transparent_xy=}, {transparent_size=}")

        # create a fitted version of input image (captured) that will cover-fit the transparent area
        image_fitted = ImageOps.fit(context.image, transparent_size, method=Image.Resampling.LANCZOS)

        # create new image
        result_image = Image.new("RGBA", image_frame.size)  # with alpha channel of same size as frame image
        result_image.paste(image_fitted, box=transparent_xy)  # first paste fitted image to result
        result_image.paste(image_frame, mask=image_frame)  # second paste frame with transparency mask on top

        context.image = result_image
        image_fitted = None
        image_frame = None

        next_step(context)


class TextStep(PipelineStep):
    def __init__(self, textstageconfig: list[models.TextsConfig]) -> None:
        self.textstageconfig = textstageconfig

    def __call__(self, context: ImageContext, next_step: NextStep) -> None:
        updated_image = context.image.copy()

        for textconfig in self.textstageconfig:
            logger.debug(f"apply text: {textconfig.text}")

            if not textconfig.text:
                # skip this one because empty.
                continue

            # check font is avail, otherwise send pipelineerror
            if not textconfig.font:
                raise PipelineError("text to apply to image but no font defined!")

            if not textconfig.font.is_file():
                raise PipelineError(f"font {textconfig.font} not found!")

            img_font = ImageFont.truetype(font=str(textconfig.font), size=textconfig.font_size)

            draw_rotated_text(
                image=updated_image,
                angle=textconfig.rotate,
                xy=(textconfig.pos_x, textconfig.pos_y),
                text=textconfig.text.format(
                    date=datetime.now().strftime("%x"),
                    time=datetime.now().strftime("%X"),
                ),
                fill=Color(textconfig.color).as_rgb_tuple(),
                font=img_font,
            )

        context.image = updated_image
        updated_image = None

        next_step(context)


class RemovebgStep(PipelineStep):
    def __init__(self, model_name: RembgModelType) -> None:
        self.model_name = model_name

    @staticmethod
    def hash_image_fast(img: Image.Image):
        h = hashlib.sha256()
        h.update(img.mode.encode())
        h.update(str(img.size).encode())
        h.update(img.tobytes())
        return h.hexdigest()

    def remove_with_cache(self, img: Image.Image, session):
        key = self.hash_image_fast(img)

        with LOCK_CACHE:
            if key in REMOVE_CACHE:
                REMOVE_CACHE.move_to_end(key)
                return REMOVE_CACHE[key]

            tms = time.monotonic()
            result = remove(img=img, session=session)
            tme = time.monotonic()

            logger.info(f"remove background using AI duration took {tme - tms:0.3}s")

            REMOVE_CACHE[key] = result
            REMOVE_CACHE.move_to_end(key)

            if len(REMOVE_CACHE) > MAX_CACHE:
                REMOVE_CACHE.popitem(last=False)

        return result

    def __call__(self, context: ImageContext, next_step: NextStep) -> None:
        global rembg_session

        try:
            # maybe in future we can reuse a session and predownload models, but as of now we start a session only on first use
            if not rembg_session or rembg_session.name() != self.model_name:
                logger.debug(f"ai background removal model {self.model_name} session initialized")
                rembg_session = new_session(model_name=self.model_name)

            cutout_image = self.remove_with_cache(img=context.image, session=rembg_session)

            assert type(cutout_image) is Image.Image
            assert cutout_image is not context.image

            context.image = cutout_image
            cutout_image = None  # only if assert abotve is correct.

        except Exception as exc:
            logger.error(f"could not remove background, error {exc}")
            # log the err, but continue anyways...

        next_step(context)


def draw_rotated_text(image: Image.Image, angle: int, xy: tuple[int, int], text: str, fill, *args, **kwargs):
    """Draw text at an angle into an image, takes the same arguments
        as Image.text() except for:

    :param image: Image to write text into
    :param angle: Angle to write text at
    """

    # build a transparency mask large enough to hold the text
    mask = Image.new("L", image.size, 0)  # "L" = 8bit pixels, greyscale

    # add text to mask
    draw = ImageDraw.Draw(mask)
    draw.text(xy, text, 255, *args, **kwargs)

    if angle == 0:
        rotated_mask = mask
    else:
        # rotated_mask = mask.rotate(angle)
        rotated_mask = mask.rotate(
            angle=angle,
            expand=False,
            resample=Image.Resampling.BICUBIC,
        )  # pos values = counter clockwise

    # paste the appropriate color, with the text transparency mask
    colored_text_image = Image.new("RGBA", image.size, fill)
    image.paste(colored_text_image, rotated_mask)
