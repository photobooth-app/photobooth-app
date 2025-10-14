import sys
from typing import Any

from PIL import Image, ImageOps
from PIL.Image import Image as PILImage

from .session_factory import new_session
from .sessions import sessions, sessions_names
from .sessions.base import BaseSession

# ort.set_default_logger_severity(3)


def naive_cutout(img: PILImage, mask: PILImage) -> PILImage:
    """
    Perform a simple cutout operation on an image using a mask.

    This function takes a PIL image `img` and a PIL image `mask` as input.
    It uses the mask to create a new image where the pixels from `img` are
    cut out based on the mask.

    The function returns a PIL image representing the cutout of the original
    image using the mask.
    """
    empty = Image.new("RGBA", (img.size), 0)
    cutout = Image.composite(img, empty, mask)
    return cutout


def download_models(models: tuple[str, ...]) -> None:
    """
    Download models for image processing.
    """
    if len(models) == 0:
        print("No models specified, downloading all models")
        models = tuple(sessions_names)

    for model in models:
        session = sessions.get(model)
        if session is None:
            print(f"Error: no model found: {model}")
            sys.exit(1)
        else:
            print(f"Downloading model: {model}")
            try:
                session.download_models()
            except Exception as e:
                print(f"Error downloading model: {e}")


def remove(img: PILImage, session: BaseSession | None = None, only_mask: bool = False, *args: Any | None, **kwargs: Any | None) -> PILImage:
    """
    Remove the background from an input image.
    """

    # Fix image orientation
    ImageOps.exif_transpose(img, in_place=True)

    if session is None:
        session = new_session("u2netp", *args, **kwargs)

    mask = session.predict(img, *args, **kwargs)

    if only_mask:
        return mask
    else:
        return naive_cutout(img, mask)
