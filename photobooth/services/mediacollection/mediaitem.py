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
        f"{type.value}_{visibility}_{datetime.now().astimezone().strftime('%Y%m%d_%H%M%S-%f')}.jpg",
    )


@dataclass
class MediaItem:
    """Class for keeping track of an media item in dict database."""

    filename: str = None

    @property
    def id(self) -> str:
        return hashlib.md5(self.filename.encode("utf-8")).hexdigest()

    @property
    def caption(self) -> str:
        return Path(self.filename).stem

    @property
    def datetime(self) -> float:
        # cache useful here?
        return os.path.getmtime(self.path_full)

    @property
    def type(self) -> MediaItemTypes:
        return MediaItemTypes.IMAGE  # TODO: derive from filename

    @property
    def visible(self) -> bool:
        return True  # TODO: derive from filename

    @property
    def ext_download_url(self) -> str:
        return "placeholder, needs revision! This is not the right place. TODO: "
        # return self._config.common.EXT_DOWNLOAD_URL.format(filename=self.filename)

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

        # TODO: if filename has no information about type and visibility: raise Exception

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
