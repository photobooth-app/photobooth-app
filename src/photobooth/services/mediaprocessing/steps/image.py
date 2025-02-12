from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np
import pilgram2
from PIL import Image, ImageDraw, ImageFont, ImageOps
from pydantic_extra_types.color import Color

from ....utils.exceptions import PipelineError
from ....utils.helper import get_user_file
from ...config.models.models import TextsConfig
from ..context import ImageContext
from ..pipeline import NextStep, PipelineStep

logger = logging.getLogger(__name__)


class Pilgram2Step(PipelineStep):
    def __init__(self, filter: str) -> None:
        self.filter = filter

    def __call__(self, context: ImageContext, next_step: NextStep) -> None:
        try:
            pilgram2_filter_fun = getattr(pilgram2, self.filter)
        except Exception as exc:
            raise PipelineError(f"pilgram2 filter {self.filter} does not exist") from exc

        # apply filter
        filtered_image: Image.Image = pilgram2_filter_fun(context.image.copy())

        if context.image.mode == "RGBA":
            # remark: "P" mode is palette (like GIF) that could have a transparent color defined also
            # since we do not use transparent GIFs currently we can ignore here.
            # P would not have an alphachannel but only a transparent color defined.
            logger.debug("need to convert to rgba and readd transparency mask to filtered image")
            # get alpha from original image
            a = context.image.getchannel("A")
            # get rgb from filtered image
            r, g, b = filtered_image.split()
            # and merge both
            filtered_transparent_image = Image.merge(context.image.mode, (r, g, b, a))

            filtered_image = filtered_transparent_image
            del filtered_transparent_image

        context.image = filtered_image
        del filtered_image

        next_step(context)

    def __repr__(self) -> str:
        return self.__class__.__name__


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

    def __repr__(self) -> str:
        return self.__class__.__name__


class ImageMountStep(PipelineStep):
    def __init__(self, background_file: Path | str, reverse: bool = False) -> None:
        self.background_file = background_file
        self.reverse = reverse

    def __call__(self, context: ImageContext, next_step: NextStep) -> None:
        if not context.image.has_transparency_data:
            logger.warning("no transparency in image, fill background skipped!")
            next_step(context)
            return  # needed, otherwise remaining code will be executed after returning from next_step

        # check font is avail, otherwise send pipelineerror - so we can recover and continue
        # default font Roboto comes with app, fallback to that one if avail
        try:
            background_path = get_user_file(self.background_file)
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

    def __repr__(self) -> str:
        return self.__class__.__name__


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
            frame_path = get_user_file(self.frame_file)
            # convert to rgba because there could be paletted PNGs in mode P but still with alpha in info.transparency.
            # converting to RGBA moves info.transparency to actual channel and handling is easy
            image_frame = Image.open(frame_path).convert("RGBA")
            logger.info(f"loaded {frame_path=}")
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

        # some debug output - may help user to improve aspect ratio of capture and transparent area to avoid loose too much information
        ratio_original = float(context.image.size[1]) / context.image.size[0]
        ratio_fitted = float(image_fitted.size[1]) / image_fitted.size[0]
        logger.info(f"captured image fitted to {image_fitted.size=}, original capture was {context.image.size=}")
        logger.debug(f"{ratio_original=}, {ratio_fitted=}")

        # create new image
        result_image = Image.new("RGBA", image_frame.size)  # with alpha channel of same size as frame image
        result_image.paste(image_fitted, box=transparent_xy)  # first paste fitted image to result
        result_image.paste(image_frame, mask=image_frame)  # second paste frame with transparency mask on top

        context.image = result_image
        image_fitted = None
        image_frame = None

        next_step(context)

    def __repr__(self) -> str:
        return self.__class__.__name__


class TextStep(PipelineStep):
    def __init__(self, textstageconfig: list[TextsConfig]) -> None:
        self.textstageconfig = textstageconfig

    def __call__(self, context: ImageContext, next_step: NextStep) -> None:
        updated_image = context.image.copy()

        for textconfig in self.textstageconfig:
            logger.debug(f"apply text: {textconfig=}")

            if not textconfig.text:
                # skip this one because empty.
                continue

            # check font is avail, otherwise send pipelineerror - so we can recover and continue
            # default font Roboto comes with app, fallback to that one if avail
            try:
                font_path = get_user_file(textconfig.font)
            except FileNotFoundError as exc:
                logger.exception(exc)
                raise PipelineError(f"font {str(textconfig.font)} not found!") from exc

            img_font = ImageFont.truetype(font=str(font_path), size=textconfig.font_size)

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

    def __repr__(self) -> str:
        return self.__class__.__name__


class RemoveChromakeyStep(PipelineStep):
    """
    References:
        choose hsv parameters: https://docs.opencv.org/4.x/df/d9d/tutorial_py_colorspaces.html
        https://stackoverflow.com/questions/10948589/choosing-the-correct-upper-and-lower-hsv-boundaries-for-color-detection-withcv/48367205#48367205
        https://stackoverflow.com/questions/48109650/how-to-detect-two-different-colors-using-cv2-inrange-in-python-opencv
        https://www.geeksforgeeks.org/opencv-invert-mask/
        https://stackoverflow.com/questions/51719472/remove-green-background-screen-from-image-using-opencv-python
        https://docs.opencv.org/3.4/d9/d61/tutorial_py_morphological_ops.html

    Args:
        pil_image (Image): _description_

    Returns:
        Image: _description_
    """

    def __init__(self, keycolor: int, tolerance: int) -> None:
        self.keycolor = keycolor
        self.tolerance = tolerance

    def __call__(self, context: ImageContext, next_step: NextStep) -> None:
        # constants derived from parameters
        dilate_pixel = 4
        blur_pixel = 2
        keycolor_range_min_hsv = ((self.keycolor) / 2 - self.tolerance, 50, 50)
        keycolor_range_max_hsv = ((self.keycolor) / 2 + self.tolerance, 255, 255)

        def convert_from_cv2_to_image(img: np.ndarray) -> Image.Image:
            return Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGRA2RGBA))

        def convert_from_image_to_cv2(img: Image.Image) -> np.ndarray:
            return cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)

        frame = convert_from_image_to_cv2(context.image)
        ## convert to hsv
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

        # mask of green
        mask = cv2.inRange(hsv, np.array(keycolor_range_min_hsv), np.array(keycolor_range_max_hsv))
        # remove noise/false positives within people area
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((dilate_pixel, dilate_pixel), np.uint8))
        # dilate mask a bit to remove bit more when blurred
        mask = cv2.dilate(mask, np.ones((dilate_pixel, dilate_pixel), np.uint8), iterations=1)

        # Inverting the mask
        mask_inverted = cv2.bitwise_not(mask)

        # enhance edges by blur# blur threshold image
        blur = cv2.GaussianBlur(mask_inverted, (0, 0), sigmaX=blur_pixel, sigmaY=blur_pixel, borderType=cv2.BORDER_DEFAULT)

        # actually remove the background (so if transparency is ignored later in processing,
        # the removed parts are black instead just return)
        result = cv2.bitwise_and(frame, frame, mask=blur)
        # create result with transparent channel
        result = cv2.cvtColor(result, cv2.COLOR_BGR2BGRA)
        result[:, :, 3] = blur  # add mask to image as alpha channel

        context.image = convert_from_cv2_to_image(result)
        frame = None
        mask = None
        mask_inverted = None
        blur = None
        result = None

        next_step(context)

    def __repr__(self) -> str:
        return self.__class__.__name__


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
