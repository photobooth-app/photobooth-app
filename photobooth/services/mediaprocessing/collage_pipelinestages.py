import logging

from PIL import Image, ImageOps

from ...appconfig import CollageMergeDefinition
from ...utils.exceptions import PipelineError
from .pipelinestages_utils import get_user_file, rotate

logger = logging.getLogger(__name__)


def merge_collage_stage(
    canvas: Image.Image,
    captured_images: list[Image.Image],
    collage_merge_definition: list[CollageMergeDefinition],
) -> Image.Image:
    """ """

    total_images_in_collage = len(collage_merge_definition)
    no_captured_images = len(captured_images)
    no_predefined_images = len([item.predefined_image for item in collage_merge_definition if item.predefined_image])

    assert canvas.mode == "RGBA"  # ensure were always operating on img with alpha channel
    assert total_images_in_collage == (no_captured_images + no_predefined_images)  # ensure numbers are right

    collage_images: list[Image.Image] = []
    for _definition in collage_merge_definition:
        if _definition.predefined_image:
            try:
                collage_images.append(Image.open(get_user_file(_definition.predefined_image)))
            except FileNotFoundError as exc:
                raise PipelineError(f"error getting predefined file {exc}") from exc
        else:
            collage_images.append(captured_images.pop(0))

    if len(collage_images) != total_images_in_collage:
        raise PipelineError("collage images no not equal to total_images_in_collage requested!")

    for index, _definition in enumerate(collage_merge_definition):
        logger.debug(_definition)
        _image = collage_images[index]
        _image = ImageOps.fit(
            _image,
            (_definition.width, _definition.height),
            method=Image.Resampling.LANCZOS,
        )  # or contain?
        _image, offset_x, offset_y = rotate(_image, _definition.rotate)

        canvas.paste(_image, (_definition.pos_x - offset_x, _definition.pos_y - offset_y))

    return canvas
