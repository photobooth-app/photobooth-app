from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image


@dataclass
class ImageContext:
    image: Image.Image = None


@dataclass
class CollageContext:
    canvas: Image.Image = None
    images: list[Image.Image] = field(default_factory=list)


@dataclass
class AnimationContext:
    images: list[Image.Image] = field(default_factory=list)


@dataclass
class VideoContext:
    video_in: Path = None
    video_processed: Path = None
