from pathlib import Path

from PIL import Image

DATA_USER_PATH = "./data/user/"


def get_image(filepath: Path) -> Image.Image:
    # check image is avail, otherwise send pipelineerror - so we can recover and continue
    # default image comes with app, fallback to that one if avail
    img_user_path = Path(DATA_USER_PATH, filepath)
    img_assets_path = (
        Path(__file__)
        .parent.resolve()
        .joinpath(
            Path(
                "assets",
                filepath,
            )
        )
    )
    img_path = img_user_path if img_user_path.is_file() else img_assets_path
    if not img_path.is_file():
        raise FileNotFoundError(f"image {str(img_user_path)} not found!")

    img = Image.open(img_path)
    return img


def rotate(image: Image.Image, angle: int = 0) -> (Image.Image, int, int):
    if angle == 0:
        return image, 0, 0

    _rotated_image = image.convert("RGBA").rotate(
        angle=angle,
        expand=True,
    )  # pos values = counter clockwise

    # https://github.com/python-pillow/Pillow/issues/4556
    offset_x = int(_rotated_image.width / 2 - image.width / 2)
    offset_y = int(_rotated_image.height / 2 - image.height / 2)

    return _rotated_image, offset_x, offset_y
