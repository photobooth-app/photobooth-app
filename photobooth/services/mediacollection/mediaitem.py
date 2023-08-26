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

from ...appconfig import AppConfig

logger = logging.getLogger(__name__)

DATA_PATH = "./data/"
# as from image source
PATH_ORIGINAL = "".join([DATA_PATH, "original/"])
# represents unaltered data from image source in S/M/L
PATH_UNPROCESSED = "".join([DATA_PATH, "unprocessed/"])
# represents pipeline-applied data of images
PATH_PROCESSED = "".join([DATA_PATH, "processed/"])

PATH_FULL_UNPROCESSED = "".join([PATH_UNPROCESSED, "full/"])
PATH_PREVIEW_UNPROCESSED = "".join([PATH_UNPROCESSED, "preview/"])
PATH_THUMBNAIL_UNPROCESSED = "".join([PATH_UNPROCESSED, "thumbnail/"])

PATH_FULL = "".join([PATH_PROCESSED, "full/"])
PATH_PREVIEW = "".join([PATH_PROCESSED, "preview/"])
PATH_THUMBNAIL = "".join([PATH_PROCESSED, "thumbnail/"])


class MediaItemTypes(str, Enum):
    IMAGE = "image"
    COLLAGE = "collage"
    VIDEO = "video"


def get_new_filename(type: MediaItemTypes = MediaItemTypes.IMAGE, visibility: bool = True) -> Path:
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

    # For call to str(). Prints readable form
    def __str__(self):
        return f"MediaItem Id: {self.id}, filename {self.filename}"

    def __repr__(self):
        return f"MediaItem Id: {self.id}, filename {self.filename}"

    @property
    def id(self) -> str:
        return hashlib.md5(self.filename.encode("utf-8")).hexdigest()

    @property
    def caption(self) -> str:
        return get_caption(self.filename)

    @property
    def datetime(self) -> float:
        return os.path.getmtime(self.path_original)

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
    def path_full_unprocessed(self) -> Path:
        """filepath of media item full resolution from device but unprocessed, used to reapply pipline chosen by user"""
        return Path(PATH_FULL_UNPROCESSED, self.filename)

    @property
    def path_full(self) -> Path:
        """filepath of media item full resolution from device but processed, example background/beautyfilter
        internal use in imagedb"""
        return Path(PATH_FULL, self.filename)

    @property
    def path_preview_unprocessed(self) -> Path:
        """filepath of media item preview resolution scaled represents full_unprocessed
        internal use in imagedb"""
        return Path(PATH_PREVIEW_UNPROCESSED, self.filename)

    @property
    def path_preview(self) -> Path:
        """filepath of media item preview resolution scaled represents full
        internal use in imagedb"""
        return Path(PATH_PREVIEW, self.filename)

    @property
    def path_thumbnail_unprocessed(self) -> Path:
        """filepath of media item thumbnail resolution scaled represents full_unprocessed
        internal use in imagedb"""
        return Path(PATH_THUMBNAIL_UNPROCESSED, self.filename)

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

    @property
    def share_url(self) -> str:
        """share url for example to use in qr code"""

        # exception here for now to use appconfig like this not via container - maybe find better solution in future.
        # config changes are not reflected like this, always needs restart
        return f"{AppConfig().common.shareservice_url}?action=download&id={self.id}"

    def __post_init__(self):
        if not self.filename:
            raise ValueError("Filename must be given")

        # if filename has no information about type and visibility: raise Exception
        if not (len(split_filename(self.filename)) == 3):
            raise ValueError(f"the original_file {self.filename} is not a valid filename - ignored")

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
            and (self.path_full_unprocessed).is_file()
            and (self.path_preview_unprocessed).is_file()
            and (self.path_thumbnail_unprocessed).is_file()
        ):
            raise FileNotFoundError(f"the imageset {self.filename=} is incomplete")

    def asdict(self) -> dict:
        """Returns a dict including all properties, excluding __xx__ and other callable functions.
        reference: https://stackoverflow.com/a/51734064

        #TODO: could be improved by reducing the number of properies (for URL and Path) by apply .as_posix here.
        # TODO: seems to have bad performance :(

        Returns:
            dict: MediaItems
        """
        return {
            prop: getattr(self, prop)
            for prop in dir(self)
            if (
                not prop.startswith("__")  # no privates
                and not callable(getattr(__class__, prop, None))  # no callables
                and not isinstance(getattr(self, prop), Path)  # no path instances (not json.serializable)
            )
        }
