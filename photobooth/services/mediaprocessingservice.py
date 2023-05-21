"""
Handle all media collection related functions
"""
import io
import logging

from PIL import Image
from pymitter import EventEmitter
from turbojpeg import TurboJPEG

from ..appconfig import AppConfig, EnumPilgramFilter
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

    def apply_pipeline_1pic(self, mediaitem: MediaItem):
        """always apply preconfigured pipeline."""

        ## start: load original file
        image = Image.open(mediaitem.path_original)

        ## stage 1: remove background

        ## stage 2: beauty
        # TODO: image = beauty_stage(image)

        ## stage 3: text overlay
        try:
            image = text_stage(
                image, textstageconfig=self._config.mediaprocessing.pic1_text_overlay
            )
        except PipelineError as exc:
            logger.error(
                f"apply text_stage failed, reason: {exc}. stage not applied, but continue"
            )

        ## stage 4: pilgram filter
        if (
            self._config.mediaprocessing.pic1_filter
            and not self._config.mediaprocessing.pic1_filter
            == EnumPilgramFilter.original
        ):
            try:
                image = pilgram_stage(
                    image, self._config.mediaprocessing.pic1_filter.value
                )
            except PipelineError as exc:
                logger.error(
                    f"apply pilgram_stage failed, reason: {exc}. stage not applied, but continue"
                )

        ## final: save result
        image.save(
            mediaitem.path_full,
            quality=self._config.common.HIRES_STILL_QUALITY,
            optimize=True,
        )

    def apply_pipeline_collage(self):
        """always apply preconfigured pipeline."""
        raise NotImplementedError

    def apply_pipeline_video(self):
        """there will probably be no video pipeline or needs to be handled different. focus on images in these pipelines now"""
        raise NotImplementedError

    def ensure_scaled_repr_created(self, mediaitem: MediaItem):
        try:
            mediaitem.fileset_valid()
        except FileNotFoundError:
            # MediaItem raises FileNotFoundError if original/full/preview/thumb is missing.
            self._logger.debug(
                f"file {mediaitem.filename} misses its scaled versions, try to create now"
            )

            # try create missing preview/thumbnail and retry. otherwise fail completely
            try:
                self.create_scaled_repr(mediaitem)
            except (FileNotFoundError, PermissionError, OSError) as exc:
                self._logger.error(
                    f"file {mediaitem.filename} processing failed. {exc}"
                )
                raise exc

    def create_scaled_repr(self, mediaitem: MediaItem):
        """_summary_

        Args:
            buffer_full (_type_): _description_
            filepath (_type_): _description_
        """

        # read fullres version
        if mediaitem.path_full.is_file():
            # if full version exists, there is a pipeline applied to that file and needs resized
            with open(mediaitem.path_full, "rb") as file:
                buffer_in = file.read()
        else:
            # if full version NOT exists, just copy to full to be failsafe - usually a full version should exist.
            with open(mediaitem.path_original, "rb") as file:
                buffer_in = file.read()

            logger.warning(
                "full sized file with pipeline applied not found. creating full sized img but no pipeline applied."
            )
            ## full version, no pipeline applied, just to not fail
            with open(mediaitem.path_full, "wb") as file:
                file.write(buffer_in)

        ## preview version
        buffer_preview = self.resize_jpeg(
            buffer_in,
            self._config.common.PREVIEW_STILL_QUALITY,
            self._config.common.PREVIEW_STILL_WIDTH,
        )
        with open(mediaitem.path_preview, "wb") as file:
            file.write(buffer_preview)

        ## thumbnail version
        buffer_thumbnail = self.resize_jpeg(
            buffer_in,
            self._config.common.THUMBNAIL_STILL_QUALITY,
            self._config.common.THUMBNAIL_STILL_WIDTH,
        )
        with open(mediaitem.path_thumbnail, "wb") as file:
            file.write(buffer_thumbnail)

        try:
            mediaitem.fileset_valid()
        except Exception as exc:
            logger.warning("something went wrong creating scaled versions!")
            raise exc

        logger.debug(
            f"filesizes orig/full: {round(len(buffer_in)/1024,1)}kb "
            f"preview: {round(len(buffer_preview)/1024,1)}kb "
            f"thumbnail: {round(len(buffer_thumbnail)/1024,1)}kb"
        )

        logger.info(f"created and saved scaled media items for {mediaitem.filename=}")

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
        scale_factor_turbojpeg = min(
            enumerate(factor_list), key=lambda x: abs(x[1] - scaling_factor)
        )
        logger.debug(
            f"determined scale factor: {scale_factor_turbojpeg[1]},"
            f"input img width {width}, target img width {scaled_min_width}"
        )

        buffer_out = turbojpeg.scale_with_quality(
            buffer_in,
            scaling_factor=allowed_list[scale_factor_turbojpeg[0]],
            quality=quality,
        )
        return buffer_out
