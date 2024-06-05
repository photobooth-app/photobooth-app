"""
Handle all media collection related functions
"""

import io
import logging
import os
import time
from pathlib import Path

from PIL import Image
from pydantic_extra_types.color import Color
from turbojpeg import TurboJPEG

from ..utils.exceptions import PipelineError
from ..utils.helper import get_user_file
from .baseservice import BaseService
from .config import appconfig
from .config.groups.actions import AnimationProcessing, CollageProcessing, VideoProcessing
from .config.models.models import SinglePictureDefinition, TextsConfig
from .mediacollection.mediaitem import MediaItem, MediaItemTypes
from .mediaprocessing.animation_pipelinestages import align_sizes_stage
from .mediaprocessing.collage_pipelinestages import merge_collage_stage
from .mediaprocessing.image_pipelinestages import (
    image_fill_background_stage,
    image_frame_stage,
    image_img_background_stage,
    pilgram_stage,
    removechromakey_stage,
    text_stage,
)
from .mediaprocessing.video_pipelinestages import boomerang_stage
from .sseservice import SseService

turbojpeg = TurboJPEG()
logger = logging.getLogger(__name__)


# TODO: consider resampling filter change:
# https://pillow.readthedocs.io/en/latest/handbook/concepts.html#filters-comparison-table


class MediaprocessingService(BaseService):
    """Handle all image related stuff"""

    def __init__(self, sse_service: SseService):
        super().__init__(sse_service)

    def _apply_stage_removechromakey(self, input_image: Image.Image) -> Image.Image:
        try:
            return removechromakey_stage(
                input_image,
                appconfig.mediaprocessing.removechromakey_keycolor,
                appconfig.mediaprocessing.removechromakey_tolerance,
            )
        except PipelineError as exc:
            logger.error(f"apply removechromakey_stage failed, reason: {exc}. stage not applied, but continue")

        # always return input_image as backup if pipeline failed
        return input_image

    def _apply_stage_pilgram(self, input_image: Image.Image, filter: str) -> Image.Image:
        if (filter is not None) and (filter != "original"):
            try:
                return pilgram_stage(input_image, filter)
            except PipelineError as exc:
                logger.error(f"apply pilgram_stage failed, reason: {exc}. stage not applied, but continue")

        # always return input_image as backup if pipeline failed
        return input_image

    def _apply_stage_fill_background(self, input_image: Image.Image, color: Color) -> Image.Image:
        try:
            return image_fill_background_stage(input_image, color)
        except PipelineError as exc:
            logger.error(f"apply image_fill_background_stage failed, reason: {exc}. stage not applied, but continue")

        # always return input_image as backup if pipeline failed
        return input_image

    def _apply_stage_img_background(self, input_image: Image.Image, file: str, reverse: bool = False) -> Image.Image:
        try:
            return image_img_background_stage(input_image, file, reverse)
        except PipelineError as exc:
            logger.error(f"apply image_img_background_stage failed, reason: {exc}. stage not applied, but continue")

        # always return input_image as backup if pipeline failed
        return input_image

    def _apply_stage_img_frame(self, input_image: Image.Image, file: str) -> Image.Image:
        try:
            return image_frame_stage(input_image, file)
        except PipelineError as exc:
            logger.error(f"apply image_frame_stage failed, reason: {exc}. stage not applied, but continue")

        # always return input_image as backup if pipeline failed
        return input_image

    def _apply_stage_texts(self, input_image: Image.Image, texts: TextsConfig) -> Image.Image:
        try:
            return text_stage(input_image, textstageconfig=texts)
        except PipelineError as exc:
            logger.error(f"apply text_stage failed, reason: {exc}. stage not applied, but continue")

        # always return input_image as backup if pipeline failed
        return input_image

    @staticmethod
    def get_filter_preview(
        mediaitem: MediaItem,
        filter: str = None,
    ) -> io.BytesIO:
        buffer_preview_pipeline_applied = io.BytesIO()

        # check for type. only specific types can have a filter applied by user
        if mediaitem.media_type not in (MediaItemTypes.image, MediaItemTypes.collageimage, MediaItemTypes.animationimage):
            raise ValueError(f"Filter can't be applied for media_type={mediaitem.media_type}!")

        try:
            image = Image.open(mediaitem.path_thumbnail_unprocessed)

            if not (filter is None or filter == "original"):
                image = pilgram_stage(image, filter)

            if image.mode == "P":  # convert GIF palette to RGB so it can be stored as jpeg
                image = image.convert("RGB")
            image.save(buffer_preview_pipeline_applied, format="jpeg", quality=80, optimize=False)

        except Exception as exc:
            logger.error(f"apply pilgram_stage failed, reason: {exc}.")
            raise exc

        return buffer_preview_pipeline_applied

    def process_image_collageimage_animationimage(self, mediaitem: MediaItem):
        """
        Unified handling of images that are just one single capture: 1pictaken (singleimages) and stills that are used in collages or animation
        Since config is different and also can depend on the current number of the image in the capture sequence,
        the config has to be determined externally.

        Performs following steps:
        - determine type of image by mediatype media_type (singleimage, collageimage, animationimage), otherwise -> fail!
        - get config for that type.
        - process it (all processes are the same, just config is different source)
        """

        # get config from mediaitem, that is passed as json dict (model_dump) along with it
        _config = SinglePictureDefinition(**mediaitem._config)

        image = Image.open(mediaitem.path_full_unprocessed)

        # go walking through the pipeline applying stages
        tms = time.time()
        number_stages_applied: int = 0  # if False in the end, just copy fileset instead
        ## stage: new background shining through transparent parts (or extended frame)

        ## stage 1: remove background
        if appconfig.mediaprocessing.removechromakey_enable:
            image = self._apply_stage_removechromakey(image)
            number_stages_applied += 1

        ## stage: pilgram filter
        if _config.filter and _config.filter.value and _config.filter.value != "original":
            image = self._apply_stage_pilgram(image, _config.filter.value)
            number_stages_applied += 1

        ## stage: new background shining through transparent parts (or extended frame)
        if _config.fill_background_enable:
            image = self._apply_stage_fill_background(image, _config.fill_background_color)
            number_stages_applied += 1

        ## stage: new background image behin transparent parts (or extended frame)
        if _config.img_background_enable:
            image = self._apply_stage_img_background(image, _config.img_background_file)
            number_stages_applied += 1

        ## stage: new image in front of transparent parts (or extended frame)
        if _config.img_frame_enable:
            image = self._apply_stage_img_frame(image, _config.img_frame_file)
            number_stages_applied += 1

        ## stage: text overlay
        if _config.texts_enable:
            image = self._apply_stage_texts(image, _config.texts)
            number_stages_applied += 1

        logger.info(f"{number_stages_applied} stages applied in: {round((time.time() - tms), 2)}s")

        if number_stages_applied == 0:
            logger.debug("no stages applied, reusing the unprocessed files as processed files.")
            mediaitem.copy_fileset_processed()
        else:
            ## final: save full result and create scaled versions
            tms = time.time()
            image = image.convert("RGB") if image.mode in ("RGBA", "P") else image
            buffer_full_pipeline_applied = io.BytesIO()
            image.save(buffer_full_pipeline_applied, format="jpeg", quality=appconfig.mediaprocessing.HIRES_STILL_QUALITY, optimize=True)

            mediaitem.create_fileset_processed(buffer_full_pipeline_applied.getbuffer())

            logger.info(f"save processed image and create scaled versions took {round((time.time() - tms), 2)}s")

        return mediaitem

    def process_video(self, video_in: Path, mediaitem: MediaItem):
        """apply preconfigured pipeline."""

        tms = time.time()
        video_proc: Path = video_in

        # get config from mediaitem, that is passed as json dict (model_dump) along with it
        _config = VideoProcessing(**mediaitem._config)

        ## stage: boomerang video
        if _config.boomerang:
            logger.info("boomerang stage to apply")
            video_proc = boomerang_stage(video_proc)

        # create final video
        os.rename(video_proc, mediaitem.path_original)
        mediaitem.create_fileset_unprocessed()
        mediaitem.copy_fileset_processed()

        logger.info(f"-- process time: {round((time.time() - tms), 2)}s to create scaled versions")

    def create_collage(self, captured_mediaitems: list[MediaItem], mediaitem: MediaItem):
        """apply preconfigured pipeline."""

        tms = time.time()

        # get config from mediaitem, that is passed as json dict (model_dump) along with it
        _config = CollageProcessing(**mediaitem._config)

        ## prepare: create canvas
        canvas_size = (_config.canvas_width, _config.canvas_height)
        canvas = Image.new("RGBA", canvas_size, color=None)

        ## stage: merge captured images and predefined to one image with transparency
        # get all images to process
        collage_images: list[Image.Image] = []
        _captured_mediaitems = captured_mediaitems.copy()

        for _definition in _config.merge_definition:
            if _definition.predefined_image:
                try:
                    predefined_image = Image.open(get_user_file(_definition.predefined_image))

                    # apply filter to predefined imgs here. captured images get processed during capture already.
                    if _definition.filter and _definition.filter.value and _definition.filter.value != "original":
                        predefined_image = self._apply_stage_pilgram(predefined_image, _definition.filter.value)

                    collage_images.append(predefined_image)
                except FileNotFoundError as exc:
                    raise PipelineError(f"error getting predefined file {exc}") from exc
            else:
                collage_images.append(Image.open(_captured_mediaitems.pop(0).path_full))

        # merge to one canvas
        try:
            canvas = merge_collage_stage(canvas, collage_images, _config.merge_definition)
        except PipelineError as exc:
            logger.error(f"apply merge_collage_stage failed, reason: {exc}. stage not applied, abort")
            raise RuntimeError("abort processing due to pipelineerror") from exc
        logger.info(f"-- process time: {round((time.time() - tms), 2)}s to create collage original")

        ## apply pipelines
        ## stage: new background shining through transparent parts (or extended frame)
        if _config.canvas_fill_background_enable:
            canvas = self._apply_stage_fill_background(canvas, _config.canvas_fill_background_color)

        ## stage: new background image behind transparent parts (or extended frame)
        if _config.canvas_img_background_enable:
            canvas = self._apply_stage_img_background(canvas, _config.canvas_img_background_file)

        ## stage: new image in front of transparent parts (or extended frame)
        if _config.canvas_img_front_enable:
            canvas = self._apply_stage_img_background(canvas, _config.canvas_img_front_file, reverse=True)

        ## stage: text overlay
        if _config.canvas_texts_enable:
            canvas = self._apply_stage_texts(canvas, _config.canvas_texts)

        ## create mediaitem
        canvas = canvas.convert("RGB") if canvas.mode in ("RGBA", "P") else canvas
        canvas.save(mediaitem.path_original, format="jpeg", quality=appconfig.mediaprocessing.HIRES_STILL_QUALITY, optimize=True)

        # create scaled versions (unprocessed and processed are same here for now
        mediaitem.create_fileset_unprocessed()
        mediaitem.copy_fileset_processed()

        logger.info(f"-- process time: {round((time.time() - tms), 2)}s to save image and create scaled versions")

    def create_animation(self, captured_mediaitems: list[MediaItem], mediaitem: MediaItem):
        """apply preconfigured pipeline."""

        tms = time.time()

        # get config from mediaitem, that is passed as json dict (model_dump) along with it
        _config = AnimationProcessing(**mediaitem._config)

        ## prepare: create canvas
        canvas_size = (_config.canvas_width, _config.canvas_height)

        ## stage: merge captured images and predefined to one image with transparency
        # get all images to process
        animation_images: list[Image.Image] = []
        _captured_mediaitems = captured_mediaitems.copy()

        for _definition in _config.merge_definition:
            if _definition.predefined_image:
                try:
                    predefined_image = Image.open(get_user_file(_definition.predefined_image))

                    # apply filter to predefined imgs here. captured images get processed during capture already.
                    if _definition.filter and _definition.filter.value and _definition.filter.value != "original":
                        predefined_image = self._apply_stage_pilgram(predefined_image, _definition.filter.value)

                    animation_images.append(predefined_image)
                except FileNotFoundError as exc:
                    raise PipelineError(f"error getting predefined file {exc}") from exc
            else:
                animation_images.append(Image.open(_captured_mediaitems.pop(0).path_full))

        # line images up and resize to make them all fit to canvas.
        try:
            animation_images_resized = align_sizes_stage(canvas_size, animation_images)
        except PipelineError as exc:
            logger.error(f"apply align_sizes_stage failed, reason: {exc}. stage not applied, abort")
            raise RuntimeError("abort processing due to pipelineerror") from exc

        logger.info(f"-- process time: {round((time.time() - tms), 2)}s to process animation pipeline")

        ## final: save full result and create scaled versions
        tms = time.time()

        # convert to RGB and store jpeg as new original
        try:
            animation_images_resized[0].save(
                mediaitem.path_original,
                format="gif",
                save_all=True,
                append_images=animation_images_resized[1:] if len(animation_images_resized) > 1 else None,
                optimize=True,
                # duration per frame in milliseconds. integer=all frames same, list/tuple individual.
                duration=[definition.duration for definition in _config.merge_definition],
                loop=0,  # loop forever
            )
        except PipelineError as exc:
            logger.error(f"error saving animation, reason: {exc}.")
            raise RuntimeError("abort processing due to pipelineerror") from exc

        logger.info(f"-- process time: {round((time.time() - tms), 2)}s to create original")

        # create scaled versions (unprocessed and processed are same here for now
        tms = time.time()
        mediaitem.create_fileset_unprocessed()
        mediaitem.copy_fileset_processed()
        logger.info(f"-- process time: {round((time.time() - tms), 2)}s to create scaled versions")
