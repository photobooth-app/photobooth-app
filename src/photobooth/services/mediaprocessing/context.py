from dataclasses import dataclass
from pathlib import Path

from PIL import Image


@dataclass
class ImageContext:
    image: Image.Image
    preview: bool = False


@dataclass
class CollageContext:
    canvas: Image.Image
    images: list[Image.Image]


@dataclass
class AnimationContext:
    images: list[Image.Image]


@dataclass
class VideoContext:
    video_in: Path
    video_processed: Path | None = None  # set by steps so last step gives the result.


@dataclass
class MulticameraContext:
    images: list[Image.Image]
