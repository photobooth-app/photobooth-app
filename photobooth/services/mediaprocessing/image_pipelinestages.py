import logging
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np
import pilgram2
from PIL import Image, ImageFont, ImageOps
from pydantic_extra_types.color import Color

from ...utils.exceptions import PipelineError
from ...utils.helper import get_user_file
from ..config.models.models import TextsConfig
from .pipelinestages_utils import draw_rotated_text

logger = logging.getLogger(__name__)


def pilgram_stage(image: Image.Image, filter: str) -> Image.Image:
    """ """
    logger.info(f"pilgram filter stage {filter} to apply")
    try:
        algofun = getattr(pilgram2, filter)
    except Exception as exc:
        raise PipelineError(f"pilgram filter {filter} does not exist") from exc
    else:
        # apply filter
        filtered_image: Image.Image = algofun(image.copy())

        if image.mode == "RGBA":
            # remark: "P" mode is palette (like GIF) that could have a transparent color defined also
            # since we do not use transparent GIFs currently we can ignore here.
            # P would not have an alphachannel but only a transparent color defined.
            logger.debug("need to convert to rgba and readd transparency mask to filtered image")
            # get alpha from original image
            a = image.getchannel("A")
            # get rgb from filtered image
            r, g, b = filtered_image.split()
            # and merge both
            filtered_transparent_image = Image.merge(image.mode, (r, g, b, a))

            return filtered_transparent_image

        return filtered_image


def text_stage(image: Image.Image, textstageconfig: list[TextsConfig]) -> Image.Image:
    """ """
    logger.info("text stage to apply")

    for textconfig in textstageconfig:
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
            image=image,
            angle=textconfig.rotate,
            xy=(textconfig.pos_x, textconfig.pos_y),
            text=textconfig.text.format(
                date=datetime.now().strftime("%x"),
                time=datetime.now().strftime("%X"),
            ),
            fill=Color(textconfig.color).as_rgb_tuple(),
            font=img_font,
        )

    return image


def beauty_stage(image: Image.Image) -> Image.Image:
    """ """
    raise PipelineError("beauty_stage not implemented yet")


def rembg_stage(image: Image.Image) -> Image.Image:
    """ """
    raise PipelineError("rembg_stage not implemented yet")  # https://github.com/danielgatis/rembg


def removechromakey_stage(pil_image: Image.Image, keycolor: int, tolerance: int) -> Image.Image:
    """_summary_

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

    logger.info("removechromakey_stage to apply")

    # constants derived from parameters
    dilate_pixel = 4
    blur_pixel = 2
    keycolor_range_min_hsv = ((keycolor) / 2 - tolerance, 50, 50)
    keycolor_range_max_hsv = ((keycolor) / 2 + tolerance, 255, 255)

    def convert_from_cv2_to_image(img: np.ndarray) -> Image.Image:
        return Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGRA2RGBA))

    def convert_from_image_to_cv2(img: Image.Image) -> np.ndarray:
        return cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)

    frame = convert_from_image_to_cv2(pil_image)
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

    return convert_from_cv2_to_image(result)


def image_fill_background_stage(image: Image.Image, color: Color) -> Image.Image:
    """ """
    if not image.has_transparency_data:
        logger.warning("no transparency in image, background stage makes no sense to apply!")
        return image

    logger.info("image_fill_background_stage to apply")
    # force color to be of type color again, might be bug in pydantic.
    background_img = Image.new(mode=image.mode, size=image.size, color=Color(color).as_rgb_tuple())
    background_img.paste(image, mask=image)

    return background_img


def image_img_background_stage(image: Image.Image, background_file: Path | str, reverse: bool = False) -> Image.Image:
    """ """
    logger.info(f"image_img_background_stage to apply, {background_file=} {reverse=}")

    if not image.has_transparency_data:
        logger.warning("no transparency in image, background stage makes no sense to apply!")
        return image

    # check font is avail, otherwise send pipelineerror - so we can recover and continue
    # default font Roboto comes with app, fallback to that one if avail
    try:
        background_path = get_user_file(background_file)
        background_img = Image.open(background_path).convert("RGBA")
    except FileNotFoundError as exc:
        logger.exception(exc)
        raise PipelineError(f"font {str(background_file)} not found!") from exc

    # fit background image to actual image size
    # this might crop the background but fills the image fully. automatic centered.
    background_img_adjusted = ImageOps.fit(
        background_img,
        image.size,
        method=Image.Resampling.LANCZOS,
    )

    # paste the actual image to the background
    if reverse:
        # copy() to output a new image so return output is consistent between reverse True/False
        output = image.copy()
        # mount loaded file on top of image.
        output.paste(background_img_adjusted, mask=background_img_adjusted)
        return output
    else:
        # mount image on top of loaded file.
        background_img_adjusted.paste(image, mask=image)
        return background_img_adjusted


def image_frame_stage(image: Image.Image, frame_file: Path | str) -> Image.Image:
    """optimized function for use on single images.
    resulting size is derived from the frame, since frame is considered as the "master"
    detects transparent area in frame and fits captured image best as possible
    using fit-cover strategy. means captured image can loose some parts if
    aspect ratio of transparent area and captured image are not equal"""

    logger.info("image_frame_stage to apply")

    # check frame is avail, otherwise send pipelineerror
    try:
        frame_path = get_user_file(frame_file)
        # convert to rgba because there could be paletted PNGs in mode P but still with alpha in info.transparency.
        # converting to RGBA moves info.transparency to actual channel and handling is easy
        image_frame = Image.open(frame_path).convert("RGBA")
    except FileNotFoundError as exc:
        logger.exception(exc)
        raise PipelineError(f"frame {str(frame_file)} not found!") from exc

    logger.info(f"loaded {frame_path=}")

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
    image_fitted = ImageOps.fit(
        image,
        transparent_size,
        method=Image.Resampling.LANCZOS,
    )

    # some debug output - may help user to improve aspect ratio of capture and transparent area to avoid loose too much information
    ratio_original = float(image.size[1]) / image.size[0]
    ratio_fitted = float(image_fitted.size[1]) / image_fitted.size[0]
    logger.info(f"captured image fitted to {image_fitted.size=}, original capture was {image.size=}")
    logger.debug(f"{ratio_original=}, {ratio_fitted=}")

    # create new image
    result_image = Image.new("RGBA", image_frame.size)  # with alpha channel of same size as frame image
    result_image.paste(image_fitted, box=transparent_xy)  # first paste fitted image to result
    result_image.paste(image_frame, mask=image_frame)  # second paste frame with transparency mask on top

    # image_frame.show()
    # image_fitted.show()
    # result_image.show()

    return result_image
