import logging

from PIL import Image

from ...appconfig import CollageStageConfig

logger = logging.getLogger(__name__)
DATA_USER_PATH = "./data/user/"


def merge_collage_stage(
    captured_images: list[Image.Image],
    collage_merge_definition: list[CollageStageConfig],
) -> Image.Image:
    """ """

    total_images_in_collage = len(collage_merge_definition)

    image1 = captured_images[0].resize((426, 240))
    image1_size = image1.size
    new_image = Image.new("RGBA", (total_images_in_collage * image1_size[0], image1_size[1]), color=None)
    # for image_definition in collage_merge_definition:
    for index, _image in enumerate(captured_images):
        new_image.paste(_image, (index * image1_size[0], 0))

    # new_image.save("images/merged_image.jpg", "JPEG")

    # new_image.show()

    return new_image
