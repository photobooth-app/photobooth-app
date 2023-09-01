from pathlib import Path

from PIL import Image

from ...utils.exceptions import PipelineError

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
        raise PipelineError(f"image {str(img_user_path)} not found!")

    img = Image.open(img_path)
    return img
