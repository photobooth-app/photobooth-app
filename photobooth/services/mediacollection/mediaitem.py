"""
Handle all media collection related functions
"""
import hashlib
import io
import logging
import os
import shutil
import time
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from functools import cached_property
from pathlib import Path

from PIL import Image, ImageSequence, UnidentifiedImageError
from turbojpeg import TurboJPEG

from ..config import appconfig

logger = logging.getLogger(__name__)
turbojpeg = TurboJPEG()

DATA_PATH = "./media/"
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
    image = "image"  # captured single image that is NOT part of a collage (normal process)
    collage = "collage"  # canvas image that was made out of several collage_image
    collageimage = "collageimage"  # captured image that is part of a collage (so it can be treated differently in UI than other images)
    animation = "animation"  # canvas image that was made out of several animation_image
    animationimage = "animationimage"  # captured image that is part of a animation (so it can be treated differently in UI than other images)
    video = "video"  # captured video - not yet implemented


class MediaItemAllowedFileendings(str, Enum):
    """Define allowed fileendings here so it can be imported from everywhere
    Used in mediacollectionservice to initially import all existing items.

    """

    jpg = "jpg"  # images
    gif = "gif"  # animated gifs


def get_new_filename(type: MediaItemTypes = MediaItemTypes.image, visibility: bool = True) -> Path:
    filename_ending = MediaItemAllowedFileendings.jpg.value  # image, collage, collage_image, animation_image are jpg
    if type is MediaItemTypes.animation:
        # only result of animation is gif, other can be jpg because more efficient and better quality.
        filename_ending = MediaItemAllowedFileendings.gif.value
    if type is MediaItemTypes.video:
        # not yet implemented.
        filename_ending = "mjpg"

    return Path(
        PATH_ORIGINAL,
        f"{type.name}_{'show' if visibility else 'hide'}_{datetime.now().astimezone().strftime('%Y%m%d-%H%M%S-%f')}.{filename_ending}",
    )


def split_filename(filename):
    splitted = Path(filename).stem.split("_", 2)
    return splitted


def get_type(filename) -> MediaItemTypes:
    return MediaItemTypes[split_filename(filename)[0]]


def get_visibility(filename) -> bool:
    return split_filename(filename)[1].lower() in ("true", "show")


def get_caption(filename) -> str:
    return split_filename(filename)[2]


@dataclass(frozen=True)
class MediaItem:
    """Class for keeping track of an media item in dict database."""

    filename: str = None

    # For call to str(). Prints readable form
    def __str__(self):
        return f"MediaItem Id: {self.id}, filename {self.filename}"

    def __repr__(self):
        return f"MediaItem Id: {self.id}, filename {self.filename}"

    @cached_property
    def id(self) -> str:
        return hashlib.md5(self.filename.encode("utf-8")).hexdigest()

    @cached_property
    def caption(self) -> str:
        return get_caption(self.filename)

    @cached_property
    def datetime(self) -> float:
        return os.path.getmtime(self.path_original)

    @cached_property
    def media_type(self) -> MediaItemTypes:
        return get_type(self.filename)

    @cached_property
    def visible(self) -> bool:
        return get_visibility(self.filename)

    @cached_property
    def data_type(self) -> str:
        return Path(self.filename).suffix[1:]

    @cached_property
    def path_original(self) -> Path:
        """filepath of item straight from device/webcam/DSLR, totally unprocessed
        internal use in imagedb"""
        return Path(PATH_ORIGINAL, self.filename)

    @cached_property
    def path_full_unprocessed(self) -> Path:
        """filepath of media item full resolution from device but unprocessed, used to reapply pipline chosen by user"""
        return Path(PATH_FULL_UNPROCESSED, self.filename)

    @cached_property
    def path_full(self) -> Path:
        """filepath of media item full resolution from device but processed, example background/beautyfilter
        internal use in imagedb"""
        return Path(PATH_FULL, self.filename)

    @cached_property
    def path_preview_unprocessed(self) -> Path:
        """filepath of media item preview resolution scaled represents full_unprocessed
        internal use in imagedb"""
        return Path(PATH_PREVIEW_UNPROCESSED, self.filename)

    @cached_property
    def path_preview(self) -> Path:
        """filepath of media item preview resolution scaled represents full
        internal use in imagedb"""
        return Path(PATH_PREVIEW, self.filename)

    @cached_property
    def path_thumbnail_unprocessed(self) -> Path:
        """filepath of media item thumbnail resolution scaled represents full_unprocessed
        internal use in imagedb"""
        return Path(PATH_THUMBNAIL_UNPROCESSED, self.filename)

    @cached_property
    def path_thumbnail(self) -> Path:
        """filepath of media item thumbnail resolution scaled represents full
        internal use in imagedb"""
        return Path(PATH_THUMBNAIL, self.filename)

    @cached_property
    def original(self) -> str:
        """filepath of item straight from device/webcam/DSLR, totally unprocessed
        external use as urls"""
        return Path(PATH_ORIGINAL, self.filename).as_posix()

    @cached_property
    def full(self) -> str:
        """filepath of media item full resolution from device but processed, example background/beautyfilter
        external use as urls"""
        return Path(PATH_FULL, self.filename).as_posix()

    @cached_property
    def preview(self) -> str:
        """filepath of media item preview resolution scaled represents full
        external use as urls"""
        return Path(PATH_PREVIEW, self.filename).as_posix()

    @cached_property
    def thumbnail(self) -> str:
        """filepath of media item thumbnail resolution scaled represents full
        external use as urls"""
        return Path(PATH_THUMBNAIL, self.filename).as_posix()

    @cached_property
    def share_url(self) -> str:
        """share url for example to use in qr code"""

        # exception here for now to use appconfig like this not via container - maybe find better solution in future.
        # config changes are not reflected like this, always needs restart
        if appconfig.sharing.shareservice_enabled:
            # if shareservice enabled, generate URL automatically as needed:
            return f"{appconfig.sharing.shareservice_url}?action=download&id={self.id}"
        else:
            # if not, user can sync images on his own and provide a download URL:
            return appconfig.sharing.share_custom_qr_url.format(filename=self.filename)

    def __post_init__(self):
        if not self.filename:
            raise ValueError("Filename must be given")

        # if filename has no information about type and visibility: raise Exception
        if not (len(split_filename(self.filename)) == 3):
            raise ValueError(f"the original_file {self.filename} is not a valid filename - ignored")

        if not ((self.path_original).is_file()):
            raise FileNotFoundError(f"the original_file {self.filename} does not exist, cannot create mediaitem for nonexisting file")

    def fileset_valid(self) -> bool:
        return (
            (self.path_original).is_file()
            and (self.path_full).is_file()
            and (self.path_preview).is_file()
            and (self.path_thumbnail).is_file()
            and (self.path_full_unprocessed).is_file()
            and (self.path_preview_unprocessed).is_file()
            and (self.path_thumbnail_unprocessed).is_file()
        )

    def ensure_scaled_repr_created(self):
        if not self.fileset_valid():
            # MediaItem raises FileNotFoundError if original/full/preview/thumb is missing.
            logger.info(f"file {self.filename} misses its scaled versions, try to create now")

            # try create missing preview/thumbnail and retry. otherwise fail completely
            try:
                tms = time.time()

                self.create_fileset_unprocessed()
                self.copy_fileset_processed()

                logger.info(f"-- process time: {round((time.time() - tms), 2)}s to copy files")
            except Exception as exc:
                logger.error(f"file {self.filename} processing failed. {exc}")
                raise exc

    def create_fileset_unprocessed(self):
        """function that creates the scaled versions (fileset) of the unprocessed mediaitem.
        Function handles the different filetypes transparently in the most efficient way.

        Currently need to support jpeg (images, collage_images, collage, animation_images) and gif (animation)
        - jpeg most efficient is turbojpeg as per benchmark.
        - gif PIL is used

        """
        suffix = Path(PATH_ORIGINAL, self.filename).suffix

        if suffix.lower() in (".jpg", ".jpeg"):
            self._create_fileset_unprocessed_jpg()
        elif suffix.lower() == ".gif":
            self._create_fileset_unprocessed_gif()
        else:
            raise RuntimeError(f"filetype not supported {suffix}")

    def create_fileset_processed(self, buffer_in: bytes):
        """function that creates the scaled versions (fileset) of the processed mediaitem.
        Function handles the different filetypes transparently in the most efficient way.

        Currently supports jpeg only
        """

        try:
            self._create_fileset_processed_jpg(buffer_in)
        except Exception as exc:
            # fail: currently only jpeg supported. if it failed, we have a problem here.
            raise RuntimeError(f"filetype not supported, error: {exc}") from exc

    def _create_fileset_unprocessed_jpg(self):
        """create jpeg fileset in most efficient way."""

        with open(self.path_original, "rb") as file:
            buffer_in = file.read()

        ## full version
        with open(self.path_full_unprocessed, "wb") as file:
            file.write(
                self.resize_jpeg(
                    buffer_in,
                    appconfig.mediaprocessing.HIRES_STILL_QUALITY,
                    appconfig.mediaprocessing.FULL_STILL_WIDTH,
                )
            )

        ## preview version
        with open(self.path_preview_unprocessed, "wb") as file:
            file.write(
                self.resize_jpeg(
                    buffer_in,
                    appconfig.mediaprocessing.PREVIEW_STILL_QUALITY,
                    appconfig.mediaprocessing.PREVIEW_STILL_WIDTH,
                )
            )

        ## thumbnail version
        with open(self.path_thumbnail_unprocessed, "wb") as file:
            file.write(
                self.resize_jpeg(
                    buffer_in,
                    appconfig.mediaprocessing.THUMBNAIL_STILL_QUALITY,
                    appconfig.mediaprocessing.THUMBNAIL_STILL_WIDTH,
                )
            )

    def _create_fileset_processed_jpg(self, buffer_in: bytes):
        ## full version
        with open(self.path_full, "wb") as file:
            file.write(
                self.resize_jpeg(
                    buffer_in,
                    appconfig.mediaprocessing.HIRES_STILL_QUALITY,
                    appconfig.mediaprocessing.FULL_STILL_WIDTH,
                )
            )

        ## preview version
        with open(self.path_preview, "wb") as file:
            file.write(
                self.resize_jpeg(
                    buffer_in,
                    appconfig.mediaprocessing.PREVIEW_STILL_QUALITY,
                    appconfig.mediaprocessing.PREVIEW_STILL_WIDTH,
                )
            )

        ## thumbnail version
        with open(self.path_thumbnail, "wb") as file:
            file.write(
                self.resize_jpeg(
                    buffer_in,
                    appconfig.mediaprocessing.THUMBNAIL_STILL_QUALITY,
                    appconfig.mediaprocessing.THUMBNAIL_STILL_WIDTH,
                )
            )

    def _create_fileset_unprocessed_gif(self):
        """create gif fileset in most efficient way."""
        try:
            gif_sequence = Image.open(self.path_original, formats=["gif"])
        except (UnidentifiedImageError, Exception) as exc:
            logger.error(f"loading gif failed: {exc}")
            raise RuntimeError(f"filetype not supported, error: {exc}") from exc

        tms = time.time()
        self.resize_gif(
            filename=self.path_full_unprocessed,
            gif_image=gif_sequence,
            scaled_min_width=appconfig.mediaprocessing.FULL_STILL_WIDTH,
        )
        logger.info(f"-- process time: {round((time.time() - tms), 2)}s to scale full_unprocessed")

        tms = time.time()
        self.resize_gif(
            filename=self.path_preview_unprocessed,
            gif_image=gif_sequence,
            scaled_min_width=appconfig.mediaprocessing.PREVIEW_STILL_WIDTH,
        )
        logger.info(f"-- process time: {round((time.time() - tms), 2)}s to scale preview_unprocessed")

        tms = time.time()
        self.resize_gif(
            filename=self.path_thumbnail_unprocessed,
            gif_image=gif_sequence,
            scaled_min_width=appconfig.mediaprocessing.THUMBNAIL_STILL_WIDTH,
        )
        logger.info(f"-- process time: {round((time.time() - tms), 2)}s to scale thumbnail_unprocessed")

    def copy_fileset_processed(self):
        shutil.copy2(self.path_full_unprocessed, self.path_full)
        shutil.copy2(self.path_preview_unprocessed, self.path_preview)
        shutil.copy2(self.path_thumbnail_unprocessed, self.path_thumbnail)

    @staticmethod
    def resize_jpeg(buffer_in: bytes, quality: int, scaled_min_width: int):
        """scale a jpeg buffer to another buffer using turbojpeg"""
        # get original size
        with Image.open(io.BytesIO(buffer_in)) as img:
            width, _ = img.size

        scaling_factor = scaled_min_width / width

        # TurboJPEG only allows for decent factors.
        # To keep it simple, config allows freely to adjust the size from 10...100% and
        # find the real factor here:
        # possible scaling factors (TurboJPEG.scaling_factors)   (nominator, denominator)
        # limitation due to turbojpeg lib usage.
        # ({(13, 8), (7, 4), (3, 8), (1, 2), (2, 1), (15, 8), (3, 4), (5, 8), (5, 4), (1, 1),
        # (1, 8), (1, 4), (9, 8), (3, 2), (7, 8), (11, 8)})
        # example: (1,4) will result in 1/4=0.25=25% down scale in relation to
        # the full resolution picture
        allowed_list = [
            (13, 8),
            (7, 4),
            (3, 8),
            (1, 2),
            (2, 1),
            (15, 8),
            (3, 4),
            (5, 8),
            (5, 4),
            (1, 1),
            (1, 8),
            (1, 4),
            (9, 8),
            (3, 2),
            (7, 8),
            (11, 8),
        ]
        factor_list = [item[0] / item[1] for item in allowed_list]
        (index, factor) = min(enumerate(factor_list), key=lambda x: abs(x[1] - scaling_factor))

        logger.debug(f"scaling img by factor {factor}, " f"width input={width} -> target={scaled_min_width}")
        if factor > 1:
            logger.warning("scale factor bigger than 1 - consider optimize config, usually images shall shrink")

        buffer_out = turbojpeg.scale_with_quality(
            buffer_in,
            scaling_factor=allowed_list[index],
            quality=quality,
        )
        return buffer_out

    @staticmethod
    def resize_gif(filename: Path, gif_image: Image.Image, scaled_min_width: int):
        """scale a gif image sequence to another buffer using PIL"""

        # Wrap on-the-fly thumbnail generator
        def thumbnails(frames: list[Image.Image]):
            for frame in frames:
                thumbnail = frame.copy()
                thumbnail.thumbnail(size=target_size, resample=Image.Resampling.LANCZOS)
                yield thumbnail

        # to recover the original durations in scaled versions
        durations = []
        for i in range(gif_image.n_frames):
            gif_image.seek(i)
            duration = gif_image.info.get("duration", 1000)  # fallback 1sec if info not avail.
            durations.append(duration)

        # determine target size
        scaling_factor = scaled_min_width / gif_image.width
        target_size = tuple(int(dim * scaling_factor) for dim in gif_image.size)

        # Get sequence iterator
        frames = ImageSequence.Iterator(gif_image)
        resized_frames = thumbnails(frames)

        # Save output
        om = next(resized_frames)  # Handle first frame separately
        om.info = gif_image.info  # Copy original information (duration is only for first frame so on save handled separately)
        om.save(
            filename,
            format="gif",
            save_all=True,
            append_images=list(resized_frames),
            duration=durations,
            optimize=True,
            loop=0,  # loop forever
        )

        return om

    def asdict(self) -> dict:
        """
        Returns a dict including properties used for frontend gallery,
        excluding private __items__ and other callable functions. https://stackoverflow.com/a/51734064

        If iterating over whole database with lots of items, computing the properties is slow
        (~3 seconds for 1000items on i7). The data of the item does not change after being created so caching is used.
        Second time the database is .asdict'ed, time reduces from 3 seconds to ~50ms which is acceptable.

        # example output:
        # "caption": "20230826-080101-985506",
        # "data_type": "jpg",
        # "datetime": 1693029662.089048,
        # "filename": "image_True_20230826-080101-985506.jpg",
        # "full": "data/processed/full/image_True_20230826-080101-985506.jpg",
        # "id": "7c8271229631bb286a4489bc012217f2",
        # "media_type": "image",
        # "original": "data/original/image_True_20230826-080101-985506.jpg",
        # "preview": "data/processed/preview/image_True_20230826-080101-985506.jpg",
        # "share_url": "https://dl.qbooth.net/dl.php?action=download&id=7c8271229631bb286a4489bc012217f2",
        # "thumbnail": "data/processed/thumbnail/image_True_20230826-080101-985506.jpg",
        # "visible": true


        Returns:
            dict: MediaItems
        """
        out = {
            prop: getattr(self, prop)
            for prop in dir(self)
            if (
                not prop.startswith("__")  # no privates
                and not callable(getattr(__class__, prop, None))  # no callables
                and not isinstance(getattr(self, prop), Path)  # no path instances (not json.serializable)
            )
        }
        return out
