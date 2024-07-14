"""
Handle all media collection related functions
"""

import hashlib
import io
import json
import logging
import os
import shutil
import subprocess
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from functools import cached_property
from pathlib import Path
from typing import Union

from PIL import Image, ImageSequence, UnidentifiedImageError
from pydantic import BaseModel
from turbojpeg import TurboJPEG
from typing_extensions import Self

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
    video = "video"  # captured video - h264, mp4 is currently well supported in browsers it seems


class MediaItemAllowedFileendings(str, Enum):
    """Define allowed fileendings here so it can be imported from everywhere
    Used in mediacollectionservice to initially import all existing items.

    """

    jpg = "jpg"  # images
    gif = "gif"  # animated gifs
    mp4 = "mp4"  # video/h264/mp4


MEDIAITEM_TYPE_TO_FILEENDING_MAPPING = {
    MediaItemTypes.image: MediaItemAllowedFileendings.jpg,
    MediaItemTypes.collage: MediaItemAllowedFileendings.jpg,
    MediaItemTypes.collageimage: MediaItemAllowedFileendings.jpg,
    MediaItemTypes.animation: MediaItemAllowedFileendings.gif,
    MediaItemTypes.animationimage: MediaItemAllowedFileendings.jpg,
    MediaItemTypes.video: MediaItemAllowedFileendings.mp4,
}


@dataclass
class MetaDataDict:
    media_type: MediaItemTypes = None
    hide: bool = False
    config: dict = field(default_factory={})

    @classmethod
    def from_dict(cls, data: dict):
        return cls(
            media_type=data.get("media_type"),
            hide=data.get("hide"),
            config=data.get("config"),
        )


@dataclass()
class MediaItem:
    """Class for keeping track of an media item in dict database."""

    filename: str = None
    _metadata: MetaDataDict = None

    # https://www.reddit.com/r/learnpython/comments/wfitql/properly_subclassing_a_dataclass_with_a_factory/
    @classmethod
    def create(cls, metadata: MetaDataDict) -> Self:
        """to instanciate a new mediaitem when creating a new media item during a job.
        if loading files, just use MediaItem() method, which skips generating a new filename.
        """
        filename_ending = MEDIAITEM_TYPE_TO_FILEENDING_MAPPING[metadata.media_type]

        new_filename = f"{datetime.now().astimezone().strftime('%Y%m%d-%H%M%S-%f')}.{filename_ending.value}"
        kls = cls(filename=new_filename, _metadata=metadata)

        kls.persist_metadata()

        return kls

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
        return self.filename

    @cached_property
    def datetime(self) -> float:
        return os.path.getmtime(self.path_original)

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
        if appconfig.qrshare.enabled:
            # if shareservice enabled, generate URL automatically as needed:
            return f"{appconfig.qrshare.shareservice_url}?action=download&id={self.id}"
        else:
            # if not, user can sync images on his own and provide a download URL:
            return appconfig.qrshare.share_custom_qr_url.format(filename=self.filename)

    @property
    def metadata_filename(self) -> Path:
        return self.path_original.with_suffix(".json")

    @property
    def media_type(self) -> MediaItemTypes:
        return self._metadata.media_type

    @property
    def _config(self) -> dict:
        return self._metadata.config

    @_config.setter
    def _config(self, value: Union[dict, BaseModel]):
        self._metadata.config = value
        self.persist_metadata()

    @property
    def hide(self) -> bool:
        return self._metadata.hide

    @hide.setter
    def hide(self, value: bool):
        self._metadata.hide = value
        self.persist_metadata()

    def load_metadata(self):
        try:
            with open(self.metadata_filename, encoding="utf-8") as openfile:
                self._metadata = MetaDataDict.from_dict(json.load(openfile))
        except (FileNotFoundError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"no metadata found or error decoding! Error: {exc}") from exc
        except Exception as exc:
            logger.exception(exc)
            raise RuntimeError(f"unknown error loading metadata, error: {exc}") from exc

    def persist_metadata(self) -> None:
        try:
            with open(self.metadata_filename, "w", encoding="utf-8") as outfile:
                json.dump(asdict(self._metadata), outfile, indent=2)
        except Exception as exc:
            logger.warning(f"could not save job config along with image, error: {exc}")

    def __post_init__(self):
        if not self.filename:
            raise ValueError("Filename must be given")

        # if loading files, metadata is default=None
        if self._metadata is None:
            # - that means, load the data
            try:
                self.load_metadata()
            except Exception as exc:
                raise RuntimeError(f"could not load metadata, error: {exc}") from exc

            # - that means also, valid to check if original is a file, otherwise fail
            if not ((self.path_original).is_file()):
                raise FileNotFoundError(f"the original_file {self.filename} does not exist, cannot create mediaitem for nonexisting file")

    def asdict(self) -> dict:
        """
        Returns a dict including properties used for frontend gallery,
        excluding private __items__ and other callable functions. https://stackoverflow.com/a/51734064

        If iterating over whole database with lots of items, computing the properties is slow
        (~3 seconds for 1000items on i7). The data of the item does not change after being created so caching is used.
        Second time the database is .asdict'ed, time reduces from 3 seconds to ~50ms which is acceptable.

        # example output:
        # "caption": "20230826-080101-985506",
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
                not prop.startswith("_")  # no privates
                and not callable(getattr(__class__, prop, None))  # no callables
                and not isinstance(getattr(self, prop), Path)  # no path instances (not json.serializable)
            )
        }
        return out

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
        suffix = self.path_original.suffix

        if suffix.lower() in (".jpg", ".jpeg"):
            self._create_fileset_unprocessed_jpg()
        elif suffix.lower() == ".gif":
            self._create_fileset_unprocessed_gif()
        elif suffix.lower() == ".mp4":
            self._create_fileset_unprocessed_mp4()
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
        # to save some processing time the full version and original are same for gif
        shutil.copy2(self.path_original, self.path_full_unprocessed)
        logger.info(f"-- process time: {round((time.time() - tms), 2)}s to copy original to full_unprocessed")

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

    def _create_fileset_unprocessed_mp4(self):
        """create mp4 fileset in most efficient way."""

        tms = time.time()
        # to save some processing time the full version and original are same for gif
        shutil.copy2(self.path_original, self.path_full_unprocessed)
        logger.info(f"-- process time: {round((time.time() - tms), 2)}s to copy original to full_unprocessed")

        tms = time.time()
        self.resize_mp4(
            video_in=self.path_original,
            video_out=self.path_preview_unprocessed,
            scaled_min_width=appconfig.mediaprocessing.PREVIEW_STILL_WIDTH,
        )
        logger.info(f"-- process time: {round((time.time() - tms), 2)}s to scale preview_unprocessed")

        tms = time.time()
        self.resize_mp4(
            video_in=self.path_preview_unprocessed,
            video_out=self.path_thumbnail_unprocessed,
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

    @staticmethod
    def resize_mp4(video_in: Path, video_out: Path, scaled_min_width: int):
        """ """

        command_general_options = [
            "-hide_banner",
            "-loglevel",
            "info",
            "-y",
        ]
        command_video_input = [
            "-i",
            str(video_in),
        ]
        command_video_output = [
            "-filter:v",
            f"scale=min'({scaled_min_width},iw)':-2,setsar=1:1",  # no upscaling
            "-sws_flags",
            "fast_bilinear",
            "-movflags",
            "+faststart",
        ]

        ffmpeg_command = ["ffmpeg"] + command_general_options + command_video_input + command_video_output + [str(video_out)]
        try:
            subprocess.run(
                args=ffmpeg_command,
                check=True,
                env=dict(os.environ, FFREPORT="file=./log/ffmpeg-resize-last.log:level=32"),
            )
        except Exception as exc:
            logger.exception(exc)
            raise RuntimeError(f"error resizing video, error: {exc}") from exc
