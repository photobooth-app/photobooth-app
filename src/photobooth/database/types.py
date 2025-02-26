import enum
from pathlib import Path

from sqlalchemy import String, TypeDecorator


class MediaitemTypes(str, enum.Enum):
    """
    SQLalchemy persists the name, fastapi validates against the value.
    We just set name==value so it works in both worlds without any conversion.
    Ref: https://github.com/fastapi/fastapi/discussions/11098
    """

    image = "image"  # captured single image that is NOT part of a collage (normal process)
    collage = "collage"  # canvas image that was made out of several collage_image
    animation = "animation"  # canvas image that was made out of several animation_image
    video = "video"  # captured video - h264, mp4 is currently well supported in browsers it seems
    multicamera = "multicamera"  #  video - h264, mp4, result of multicamera image, example the wigglegram


class DimensionTypes(str, enum.Enum):
    """
    SQLalchemy persists the name, fastapi validates against the value.
    We just set name==value so it works in both worlds without any conversion.
    Ref: https://github.com/fastapi/fastapi/discussions/11098
    """

    full = "full"
    preview = "preview"
    thumbnail = "thumbnail"


class PathType(TypeDecorator):
    impl = String

    def process_bind_param(self, value, dialect):
        return str(value)

    def process_result_value(self, value, dialect):
        assert value is not None
        return Path(value)
