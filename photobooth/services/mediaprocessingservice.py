"""
Handle all media collection related functions
"""
import io
import logging
import shutil
import time

from PIL import Image
from pymitter import EventEmitter
from turbojpeg import TurboJPEG

from ..appconfig import AppConfig
from ..utils.exceptions import PipelineError
from .baseservice import BaseService
from .mediacollection.mediaitem import MediaItem
from .mediaprocessing.image_pipelinestages import (
    pilgram_stage,
    text_stage,
)

turbojpeg = TurboJPEG()
logger = logging.getLogger(__name__)


class MediaprocessingService(BaseService):
    """Handle all image related stuff"""

    def __init__(self, evtbus: EventEmitter, config: AppConfig):
        super().__init__(evtbus=evtbus, config=config)

    def recreate_1pic(self, mediaitem: MediaItem):
        """recreate item in case original is avail, but all else is lost for whatever reason"""
        # 1 create unprocessed images
        tms = time.time()
        self.create_scaled_unprocessed_repr(mediaitem)

        # 2  copy
        self.copy_1pic_repr(mediaitem)

        logger.info(f"-- process time: {round((time.time() - tms), 2)}s to create scaled images")

        # 3 finally ensure all is right
        try:
            mediaitem.fileset_valid()
        except Exception as exc:
            logger.warning("something went wrong creating scaled versions!")
            raise exc

    def copy_1pic_repr(self, mediaitem: MediaItem):
        tms = time.time()
        shutil.copy2(mediaitem.path_full_unprocessed, mediaitem.path_full)
        shutil.copy2(mediaitem.path_preview_unprocessed, mediaitem.path_preview)
        shutil.copy2(mediaitem.path_thumbnail_unprocessed, mediaitem.path_thumbnail)

        logger.info(f"-- process time: {round((time.time() - tms), 2)}s to copy files")

    def apply_pipeline_1pic(self, mediaitem: MediaItem, user_filter: str = None):
        """always apply preconfigured pipeline."""
        tms = time.time()

        ## pipeline is enabled, so start processing now:
        with open(mediaitem.path_full_unprocessed, "rb") as file:
            buffer_full = file.read()

        ## start: load original file
        image = Image.open(io.BytesIO(buffer_full))

        ## stage 1: remove background

        ## stage 2: beauty
        # TODO: image = beauty_stage(image)

        ## stage 3: text overlay
        try:
            image = text_stage(image, textstageconfig=self._config.mediaprocessing.pic1_text_overlay)
        except PipelineError as exc:
            logger.error(f"apply text_stage failed, reason: {exc}. stage not applied, but continue")

        ## stage 4: pilgram filter
        filter = user_filter if user_filter is not None else self._config.mediaprocessing.pic1_filter.value

        if (filter is not None) and (filter != "original"):
            try:
                image = pilgram_stage(image, filter)
            except PipelineError as exc:
                logger.error(f"apply pilgram_stage failed, reason: {exc}. stage not applied, but continue")

        logger.info(f"-- process time: {round((time.time() - tms), 2)}s to apply pipeline")

        ## final: save full result and create scaled versions
        tms = time.time()
        buffer_full_pipeline_applied = io.BytesIO()
        image.save(
            buffer_full_pipeline_applied,
            format="jpeg",
            quality=self._config.common.HIRES_STILL_QUALITY,
            optimize=True,
        )

        # save filtered full
        with open(mediaitem.path_full, "wb") as file:
            file.write(buffer_full_pipeline_applied.getbuffer())
        # save scaled preview (derived from filtered full)
        with open(mediaitem.path_preview, "wb") as file:
            file.write(self._get_preview_repr(buffer_full_pipeline_applied.getbuffer()))
        # save scaled thumbnail (derived from filtered full)
        with open(mediaitem.path_thumbnail, "wb") as file:
            file.write(self._get_thumbnail_repr(buffer_full_pipeline_applied.getbuffer()))

        logger.info(
            f"-- process time: {round((time.time() - tms), 2)}s to save processed image and create scaled versions"
        )

    def apply_pipeline_collage(self):
        """always apply preconfigured pipeline."""
        raise NotImplementedError

    def apply_pipeline_video(self):
        """
        there will probably be no video pipeline or needs to be handled different.
        focus on images in these pipelines now
        """
        raise NotImplementedError

    def ensure_scaled_repr_created(self, mediaitem: MediaItem):
        try:
            mediaitem.fileset_valid()
        except FileNotFoundError:
            # MediaItem raises FileNotFoundError if original/full/preview/thumb is missing.
            self._logger.debug(f"file {mediaitem.filename} misses its scaled versions, try to create now")

            # try create missing preview/thumbnail and retry. otherwise fail completely
            try:
                self.recreate_1pic(mediaitem)
            except (FileNotFoundError, PermissionError, OSError) as exc:
                self._logger.error(f"file {mediaitem.filename} processing failed. {exc}")
                raise exc

    def create_scaled_unprocessed_repr(self, mediaitem: MediaItem):
        """_summary_

        Args:
            buffer_full (_type_): _description_
            filepath (_type_): _description_
        """
        buffer_in = self._read_original(mediaitem)

        ## full version
        with open(mediaitem.path_full_unprocessed, "wb") as file:
            file.write(self._get_full_repr(buffer_in))
            logger.debug(f"{mediaitem.path_full_unprocessed=} written to disk")

        ## preview version
        with open(mediaitem.path_preview_unprocessed, "wb") as file:
            file.write(self._get_preview_repr(buffer_in))
            logger.debug(f"{mediaitem.path_preview_unprocessed=} written to disk")

        ## thumbnail version
        with open(mediaitem.path_thumbnail_unprocessed, "wb") as file:
            file.write(self._get_thumbnail_repr(buffer_in))
            logger.debug(f"{mediaitem.path_thumbnail_unprocessed=} written to disk")

        logger.info(f"created and saved scaled media items for {mediaitem.filename=}")

    def _read_original(self, mediaitem: MediaItem) -> bytes:
        with open(mediaitem.path_original, "rb") as file:
            buffer_in = file.read()

        return buffer_in

    def _get_full_repr(self, buffer_in: bytes) -> bytes:
        return self.resize_jpeg(
            buffer_in,
            self._config.common.HIRES_STILL_QUALITY,
            self._config.common.FULL_STILL_WIDTH,
        )

    def _get_preview_repr(self, buffer_in: bytes) -> bytes:
        return self.resize_jpeg(
            buffer_in,
            self._config.common.PREVIEW_STILL_QUALITY,
            self._config.common.PREVIEW_STILL_WIDTH,
        )

    def _get_thumbnail_repr(self, buffer_in: bytes) -> bytes:
        return self.resize_jpeg(
            buffer_in,
            self._config.common.THUMBNAIL_STILL_QUALITY,
            self._config.common.THUMBNAIL_STILL_WIDTH,
        )

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
