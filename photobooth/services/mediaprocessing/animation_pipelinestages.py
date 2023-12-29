import logging

from PIL import Image, ImageOps

logger = logging.getLogger(__name__)


def align_sizes_stage(
    canvas_size: tuple[int, int],
    sequence_images: list[Image.Image],
) -> list[Image.Image]:
    """ """
    sequenced_images = []

    for _image in sequence_images:
        sequenced_images.append(ImageOps.fit(_image, canvas_size, method=Image.Resampling.LANCZOS))  # or contain?

    return sequenced_images
