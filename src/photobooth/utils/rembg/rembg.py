"""
The util is very much inspired by https://github.com/danielgatis/rembg
Thank you!
"""

from typing import Any

from PIL import Image, ImageOps
from PIL.Image import Image as PILImage

from .session_factory import new_session
from .sessions.base import BaseSession


def naive_cutout(img: PILImage, mask: PILImage) -> PILImage:
    empty = Image.new("RGBA", (img.size), 0)
    cutout = Image.composite(img, empty, mask)
    return cutout


def remove(img: PILImage, session: BaseSession | None = None, only_mask: bool = False, *args: Any | None, **kwargs: Any | None) -> PILImage:
    """
    Remove the background from an input image.
    """

    # Fix image orientation
    ImageOps.exif_transpose(img, in_place=True)

    if session is None:
        session = new_session("modnet", *args, **kwargs)

    mask = session.predict(img, *args, **kwargs)

    if only_mask:
        return mask
    else:
        return naive_cutout(img, mask)
