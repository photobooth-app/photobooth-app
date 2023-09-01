"""
Handle all media collection related functions
"""
import io
import logging
import os
import time

from PIL import Image
from pymitter import EventEmitter
from turbojpeg import TurboJPEG

from ..appconfig import AppConfig
from ..utils.exceptions import PipelineError
from .baseservice import BaseService
from .mediacollection.mediaitem import MediaItem, MediaItemTypes, get_new_filename
from .mediaprocessing.collage_pipelinestages import merge_collage_stage
from .mediaprocessing.image_pipelinestages import (
    image_fill_background_stage,
    image_img_background_stage,
    pilgram_stage,
    removechromakey_stage,
    text_stage,
)

turbojpeg = TurboJPEG()
logger = logging.getLogger(__name__)


class MediaprocessingService(BaseService):
    """Handle all image related stuff"""

    def __init__(self, evtbus: EventEmitter, config: AppConfig):
        super().__init__(evtbus=evtbus, config=config)

    def apply_pipeline_1pic(self, mediaitem: MediaItem, user_filter: str = None) -> MediaItem:
        """always apply preconfigured pipeline."""

        # TODO: The whole processing should be refactored

        tms = time.time()

        ## pipeline is enabled, so start processing now:
        with open(mediaitem.path_full_unprocessed, "rb") as file:
            buffer_full = file.read()

        ## start: load original file
        image = Image.open(io.BytesIO(buffer_full))

        ## stage 1: remove background
        if (
            self._config.mediaprocessing.pic1_pipeline_enable
            and self._config.mediaprocessing.pic1_removechromakey_enable
        ):
            try:
                image = removechromakey_stage(
                    image,
                    self._config.mediaprocessing.pic1_removechromakey_keycolor,
                    self._config.mediaprocessing.pic1_removechromakey_tolerance,
                )
            except PipelineError as exc:
                logger.error(f"apply removechromakey_stage failed, reason: {exc}. stage not applied, but continue")

        ## stage: pilgram filter
        filter = user_filter if user_filter is not None else self._config.mediaprocessing.pic1_filter.value

        if self._config.mediaprocessing.pic1_pipeline_enable or user_filter:
            if (filter is not None) and (filter != "original"):
                try:
                    image = pilgram_stage(image, filter)
                except PipelineError as exc:
                    logger.error(f"apply pilgram_stage failed, reason: {exc}. stage not applied, but continue")

        ## stage: text overlay
        if self._config.mediaprocessing.pic1_pipeline_enable and self._config.mediaprocessing.pic1_text_overlay_enable:
            try:
                image = text_stage(image, textstageconfig=self._config.mediaprocessing.pic1_text_overlay)
            except PipelineError as exc:
                logger.error(f"apply text_stage failed, reason: {exc}. stage not applied, but continue")

        ## stage: new background shining through transparent parts (or extended frame)
        if (
            self._config.mediaprocessing.pic1_pipeline_enable
            and self._config.mediaprocessing.pic1_fill_background_enable
        ):
            try:
                image = image_fill_background_stage(image, self._config.mediaprocessing.pic1_fill_background_color)
            except PipelineError as exc:
                logger.error(
                    f"apply image_fill_background_stage failed, reason: {exc}. stage not applied, but continue"
                )

        ## stage: new background image behing transparent parts (or extended frame)
        if (
            self._config.mediaprocessing.pic1_pipeline_enable
            and self._config.mediaprocessing.pic1_img_background_enable
        ):
            try:
                image = image_img_background_stage(image, self._config.mediaprocessing.pic1_img_background_file)
            except PipelineError as exc:
                logger.error(f"apply image_img_background_stage failed, reason: {exc}. stage not applied, but continue")

        logger.info(f"-- process time: {round((time.time() - tms), 2)}s to apply pipeline stages")

        ## final: save full result and create scaled versions
        tms = time.time()
        buffer_full_pipeline_applied = io.BytesIO()
        if image.mode in ("RGBA", "P"):
            image = image.convert("RGB")
        image.save(
            buffer_full_pipeline_applied,
            format="jpeg",
            quality=self._config.common.HIRES_STILL_QUALITY,
            optimize=True,
        )

        mediaitem.create_fileset_processed(buffer_full_pipeline_applied.getbuffer())

        logger.info(
            f"-- process time: {round((time.time() - tms), 2)}s to save processed image and create scaled versions"
        )

        return mediaitem

    def number_of_captures_to_take_for_collage(self) -> int:
        """analyze the configuration and return the needed number of captures to take by camera.
        If there are fixed images given these do not count to the number to capture.

        Returns:
            int: number of captures
        """
        if not self._config.mediaprocessing.collage_merge_definition:
            raise PipelineError("collage definition not set up!")

        collage_merge_definition = self._config.mediaprocessing.collage_merge_definition
        # item.predefined_image None or "" are considered as to capture aka not predefined
        predefined_images = [item.predefined_image for item in collage_merge_definition if item.predefined_image]
        for predefined_image in predefined_images:
            if not predefined_image:
                # TODO: make it check isfile?
                raise PipelineError(f"predefined image {predefined_image} not found!")

        total_images_in_collage = len(collage_merge_definition)
        fixed_images = len(predefined_images)

        captures_to_take = total_images_in_collage - fixed_images

        return captures_to_take

    def apply_pipeline_collage(self, captured_mediaitems: list[MediaItem]) -> MediaItem:
        """apply preconfigured pipeline."""

        tms = time.time()

        ## stage 1:
        # merge captured images and predefined to one image with transparency
        if True:
            captured_images: list[Image.Image] = []
            for captured_mediaitem in captured_mediaitems:
                captured_images.append(Image.open(captured_mediaitem.path_full))

            try:
                merged_transparent_image = merge_collage_stage(
                    captured_images, self._config.mediaprocessing.collage_merge_definition
                )
            except PipelineError as exc:
                logger.error(f"apply merge_collage_stage failed, reason: {exc}. stage not applied, abort")
                raise RuntimeError("abort processing due to pipelineerror") from exc

        logger.info(
            f"-- process time: {round((time.time() - tms), 2)}s to save processed collage and create scaled versions"
        )

        ## stage 2:
        # fill background with solid color

        ## stage 3:
        # add frame on top (images shine through the transparent parts)

        ## stage 4:
        # add frame on top

        ## stage 5:
        # add text

        ## thats it?
        ## final: save full result and create scaled versions
        filepath_neworiginalfile = get_new_filename(type=MediaItemTypes.COLLAGE)
        image = merged_transparent_image

        tms = time.time()
        io.BytesIO()
        if image.mode in ("RGBA", "P"):
            image = image.convert("RGB")
        image.save(
            filepath_neworiginalfile,
            format="jpeg",
            quality=self._config.common.HIRES_STILL_QUALITY,
            optimize=True,
        )

        # instanciate mediaitem with new original file
        mediaitem = MediaItem(os.path.basename(filepath_neworiginalfile))

        # create scaled versions (unprocessed and processed are same here for now
        mediaitem.create_fileset_unprocessed()
        mediaitem.copy_fileset_processed()

        logger.info(
            f"-- process time: {round((time.time() - tms), 2)}s to save processed image and create scaled versions"
        )

        return mediaitem

    def apply_pipeline_video(self):
        """
        there will probably be no video pipeline or needs to be handled different.
        focus on images in these pipelines now
        """
        raise NotImplementedError
