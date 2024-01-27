from PIL import Image, ImageDraw


def rotate(image: Image.Image, angle: int = 0, expand: bool = True) -> (Image.Image, int, int):
    if angle == 0:
        # quick return, but also convert to RGBA for consistency reason in following processing
        return image.convert("RGBA"), 0, 0

    _rotated_image = image.convert("RGBA").rotate(
        angle=angle,
        expand=expand,
        resample=Image.Resampling.BICUBIC,
    )  # pos values = counter clockwise

    # https://github.com/python-pillow/Pillow/issues/4556
    offset_x = int(_rotated_image.width / 2 - image.width / 2)
    offset_y = int(_rotated_image.height / 2 - image.height / 2)

    return _rotated_image, offset_x, offset_y


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
