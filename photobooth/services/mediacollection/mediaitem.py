"""
Handle all media collection related functions
"""
import hashlib
import logging
import os
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path

logger = logging.getLogger(__name__)

DATA_PATH = "./data/"
PATH_ORIGINAL = "".join([DATA_PATH, "original/"])
PATH_FULL = "".join([DATA_PATH, "full/"])
PATH_PREVIEW = "".join([DATA_PATH, "preview/"])
PATH_THUMBNAIL = "".join([DATA_PATH, "thumbnail/"])


class MediaItemTypes(str, Enum):
    IMAGE = "image"
    COLLAGE = "collage"
    VIDEO = "video"


def get_new_filename(
    type: MediaItemTypes = MediaItemTypes.IMAGE, visibility: bool = True
) -> Path:
    return Path(
        PATH_ORIGINAL,
        f"{type.value}_{visibility}_{datetime.now().astimezone().strftime('%Y%m%d-%H%M%S-%f')}.jpg",
    )


def split_filename(filename):
    splitted = Path(filename).stem.split("_", 2)
    return splitted


def get_type(filename) -> MediaItemTypes:
    return MediaItemTypes(value=split_filename(filename)[0])


def get_visibility(filename) -> bool:
    return split_filename(filename)[1].lower() == "true"


def get_caption(filename) -> str:
    return split_filename(filename)[2]


@dataclass
class MediaItem:
    """Class for keeping track of an media item in dict database."""

    filename: str = None

    @property
    def id(self) -> str:
        return hashlib.md5(self.filename.encode("utf-8")).hexdigest()

    @property
    def caption(self) -> str:
        return get_caption(self.filename)

    @property
    def datetime(self) -> float:
        return os.path.getmtime(self.path_full)

    @property
    def media_type(self) -> MediaItemTypes:
        return get_type(self.filename)

    @property
    def visible(self) -> bool:
        return get_visibility(self.filename)

    @property
    def data_type(self) -> str:
        return Path(self.filename).suffix[1:]

    @property
    def path_original(self) -> Path:
        """filepath of item straight from device/webcam/DSLR, totally unprocessed
        internal use in imagedb"""
        return Path(PATH_ORIGINAL, self.filename)

    @property
    def path_full(self) -> Path:
        """filepath of media item full resolution from device but processed, example background/beautyfilter
        internal use in imagedb"""
        return Path(PATH_FULL, self.filename)

    @property
    def path_preview(self) -> Path:
        """filepath of media item preview resolution scaled represents full
        internal use in imagedb"""
        return Path(PATH_PREVIEW, self.filename)

    @property
    def path_thumbnail(self) -> Path:
        """filepath of media item thumbnail resolution scaled represents full
        internal use in imagedb"""
        return Path(PATH_THUMBNAIL, self.filename)

    @property
    def original(self) -> str:
        """filepath of item straight from device/webcam/DSLR, totally unprocessed
        external use as urls"""
        return Path(PATH_ORIGINAL, self.filename).as_posix()

    @property
    def full(self) -> str:
        """filepath of media item full resolution from device but processed, example background/beautyfilter
        external use as urls"""
        return Path(PATH_FULL, self.filename).as_posix()

    @property
    def preview(self) -> str:
        """filepath of media item preview resolution scaled represents full
        external use as urls"""
        return Path(PATH_PREVIEW, self.filename).as_posix()

    @property
    def thumbnail(self) -> str:
        """filepath of media item thumbnail resolution scaled represents full
        external use as urls"""
        return Path(PATH_THUMBNAIL, self.filename).as_posix()

    def __post_init__(self):
        if not self.filename:
            raise ValueError("Filename must be given")

        # if filename has no information about type and visibility: raise Exception
        if not (len(split_filename(self.filename)) == 3):
            raise ValueError(
                f"the original_file {self.filename} is not a valid filename - ignored"
            )

        if not ((self.path_original).is_file()):
            raise FileNotFoundError(
                f"the original_file {self.filename} does not exist, cannot create mediaitem for nonexisting file"
            )

    def fileset_valid(self):
        if not (
            (self.path_original).is_file()
            and (self.path_full).is_file()
            and (self.path_preview).is_file()
            and (self.path_thumbnail).is_file()
        ):
            raise FileNotFoundError(
                f"the imageset is incomplete, not adding {self.filename} to database"
            )

    def asdict(self) -> dict:
        """Returns a dict including all properties, excluding __xx__ and other callable functions.
        reference: https://stackoverflow.com/a/51734064

        #TODO: could be improved by reducing the number of properies (for URL and Path) by apply .as_posix here.

        Returns:
            dict: MediaItems
        """
        return {
            prop: getattr(self, prop)
            for prop in dir(self)
            if (
                not prop.startswith("__")  # no privates
                and not callable(getattr(__class__, prop, None))  # no callables
                and not isinstance(
                    getattr(self, prop), Path
                )  # no path instances (not json.serializable)
            )
        }
