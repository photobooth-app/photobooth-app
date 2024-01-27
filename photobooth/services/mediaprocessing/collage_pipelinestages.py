import logging

from PIL import Image, ImageOps

from ..config.groups.mediaprocessing import CollageMergeDefinition
from .pipelinestages_utils import rotate

logger = logging.getLogger(__name__)


def merge_collage_stage(
    canvas: Image.Image,
    collage_images: list[Image.Image],
    collage_merge_definition: list[CollageMergeDefinition],
) -> Image.Image:
    """ """

    assert canvas.mode == "RGBA"  # ensure were always operating on img with alpha channel
    assert len(collage_images) == len(collage_merge_definition)  # ensure numbers are right

    for index, _definition in enumerate(collage_merge_definition):
        logger.debug(_definition)
        _image = collage_images[index]
        _image = ImageOps.fit(_image, (_definition.width, _definition.height), method=Image.Resampling.LANCZOS)  # or contain?
        _image, offset_x, offset_y = rotate(_image, _definition.rotate)

        # _image needs to have an alpha channel, otherwise paste with mask=_image fails.
        # above rotate always converts to RGBA consistently now to ensure paste nevers fails.
        canvas.paste(_image, (_definition.pos_x - offset_x, _definition.pos_y - offset_y), _image)

    return canvas
