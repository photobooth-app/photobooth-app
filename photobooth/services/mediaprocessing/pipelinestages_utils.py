from pathlib import Path
from typing import Union

from PIL import Image

DATA_USER_PATH = "./data/user/"


def get_user_file(filepath: Union[Path, str]) -> Path:
    # check font is avail, otherwise send pipelineerror - so we can recover and continue
    # default font Roboto comes with app, fallback to that one if avail
    file_user_path = Path(DATA_USER_PATH, filepath)
    file_assets_path = Path(__file__).parent.resolve().joinpath(Path("assets", filepath))
    out_filepath = file_user_path if file_user_path.is_file() else file_assets_path

    if not out_filepath.is_file():
        raise FileNotFoundError(f"filepath {str(filepath)} not found!")

    return out_filepath


def rotate(image: Image.Image, angle: int = 0) -> (Image.Image, int, int):
    if angle == 0:
        return image, 0, 0

    _rotated_image = image.convert("RGBA").rotate(
        angle=angle,
        expand=True,
        resample=Image.Resampling.BICUBIC,
    )  # pos values = counter clockwise

    # https://github.com/python-pillow/Pillow/issues/4556
    offset_x = int(_rotated_image.width / 2 - image.width / 2)
    offset_y = int(_rotated_image.height / 2 - image.height / 2)

    return _rotated_image, offset_x, offset_y
