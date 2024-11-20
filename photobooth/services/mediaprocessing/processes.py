from __future__ import annotations

import io
import logging
import os
import time
import traceback
from pathlib import Path

from PIL import Image

from ..config import appconfig
from ..config.groups.actions import AnimationProcessing, CollageProcessing, MulticameraProcessing, VideoProcessing
from ..config.models.models import SinglePictureDefinition
from ..mediacollection.mediaitem import MediaItem, MediaItemTypes
from .context import AnimationContext, CollageContext, ImageContext, MulticameraContext, VideoContext
from .pipeline import NextStep, Pipeline
from .steps.animation import AlignSizesStep
from .steps.animation_collage_shared import AddPredefinedImagesStep, PostPredefinedImagesStep
from .steps.collage import MergeCollageStep
from .steps.image import FillBackgroundStep, ImageFrameStep, ImageMountStep, Pilgram2Step, RemoveChromakeyStep, TextStep
from .steps.video import BoomerangStep

logger = logging.getLogger(__name__)


def process_image_collageimage_animationimage(mediaitem: MediaItem):
    """
    Unified handling of images that are just one single capture: 1pictaken (singleimages) and stills that are used in collages or animation
    Since config is different and also can depend on the current number of the image in the capture sequence,
    the config has to be determined externally.
    """

    image = Image.open(mediaitem.path_full_unprocessed)
    config = SinglePictureDefinition(**mediaitem._config)  # get config from mediaitem, that is passed as json dict (model_dump) along with it

    context = ImageContext(image)
    steps = []

    # assemble pipeline
    if appconfig.mediaprocessing.removechromakey_enable:
        steps.append(RemoveChromakeyStep(appconfig.mediaprocessing.removechromakey_keycolor, appconfig.mediaprocessing.removechromakey_tolerance))

    if config.filter and config.filter.value and config.filter.value != "original":
        steps.append(Pilgram2Step(config.filter.value))

    if config.img_background_enable:
        steps.append(ImageMountStep(config.img_background_file))

    if config.fill_background_enable:
        steps.append(FillBackgroundStep(config.fill_background_color))

    if config.img_frame_enable:
        steps.append(ImageFrameStep(config.img_frame_file))

    if config.texts_enable:
        steps.append(TextStep(config.texts))

    # finished assembly

    # setup pipeline.
    pipeline = Pipeline[ImageContext](*steps)

    def _error_handler(error: Exception, context: ImageContext, next_step: NextStep) -> None:
        traceback.print_exception(error)
        logger.error(f"Error applying step, error: {error}")
        raise error

    # execute pipeline
    tms = time.time()
    pipeline(context, _error_handler)
    logger.info(f"process time: {round((time.time() - tms), 2)}s to process pipeline")

    # get result
    manipulated_image = context.image

    # finish up creating mediafiles representants.
    if len(steps) == 0:
        logger.debug("no stages applied, reusing the unprocessed files as processed files.")
        mediaitem.copy_fileset_processed()
    else:
        ## final: save full result and create scaled versions
        tms = time.time()
        manipulated_image = manipulated_image.convert("RGB") if manipulated_image.mode in ("RGBA", "P") else manipulated_image
        buffer_full_pipeline_applied = io.BytesIO()
        manipulated_image.save(buffer_full_pipeline_applied, format="jpeg", quality=appconfig.mediaprocessing.HIRES_STILL_QUALITY, optimize=True)

        mediaitem.create_fileset_processed(buffer_full_pipeline_applied.getbuffer())

        logger.info(f"save processed image and create scaled versions took {round((time.time() - tms), 2)}s")

    return mediaitem


def process_video(video_in: Path, mediaitem: MediaItem):
    # get config from mediaitem, that is passed as json dict (model_dump) along with it
    config = VideoProcessing(**mediaitem._config)

    context = VideoContext(video_in)
    steps = []

    if config.boomerang:
        steps.append(BoomerangStep())

    # setup pipeline.
    pipeline = Pipeline[VideoContext](*steps)

    # execute pipeline
    pipeline(context)

    # get result
    video_processed = context.video_processed

    # create final video
    tms = time.time()
    os.rename(video_processed, mediaitem.path_original)
    mediaitem.create_fileset_unprocessed()
    mediaitem.copy_fileset_processed()
    logger.info(f"-- process time: {round((time.time() - tms), 2)}s to create scaled versions")


def process_and_generate_collage(captured_mediaitems: list[MediaItem], mediaitem: MediaItem):
    # get config from mediaitem, that is passed as json dict (model_dump) along with it
    config = CollageProcessing(**mediaitem._config)

    ## prepare: create canvas and input images
    canvas_size = (config.canvas_width, config.canvas_height)
    canvas = Image.new("RGBA", canvas_size, color=None)
    collage_images: list[Image.Image] = [Image.open(_captured_mediaitems.path_full) for _captured_mediaitems in captured_mediaitems]

    context = CollageContext(canvas, collage_images)
    steps = []
    steps.append(AddPredefinedImagesStep(config.merge_definition))
    steps.append(PostPredefinedImagesStep(config.merge_definition))
    steps.append(MergeCollageStep(config.merge_definition))
    pipeline = Pipeline[CollageContext](*steps)
    pipeline(context)

    canvas = context.canvas

    ## phase 2
    context = ImageContext(canvas)
    steps = []

    # assemble pipeline

    if config.canvas_img_background_enable:
        steps.append(ImageMountStep(canvas, config.canvas_img_background_file))

    if config.canvas_fill_background_enable:
        steps.append(FillBackgroundStep(config.canvas_fill_background_color))

    if config.canvas_img_front_enable:
        steps.append(ImageMountStep(config.canvas_img_front_file, reverse=True))

    if config.canvas_texts_enable:
        steps.append(TextStep(config.canvas_texts))

    pipeline = Pipeline[ImageContext](*steps)
    pipeline(context)

    canvas = context.image

    ## create mediaitem
    canvas = canvas.convert("RGB") if canvas.mode in ("RGBA", "P") else canvas
    canvas.save(mediaitem.path_original, format="jpeg", quality=appconfig.mediaprocessing.HIRES_STILL_QUALITY, optimize=True)

    # create scaled versions (unprocessed and processed are same here for now
    mediaitem.create_fileset_unprocessed()
    mediaitem.copy_fileset_processed()


def process_and_generate_animation(captured_mediaitems: list[MediaItem], mediaitem: MediaItem):
    # get config from mediaitem, that is passed as json dict (model_dump) along with it
    config = AnimationProcessing(**mediaitem._config)

    ## prepare: create canvas
    canvas_size = (config.canvas_width, config.canvas_height)

    ## stage: merge captured images and predefined to one image with transparency
    animation_images: list[Image.Image] = [Image.open(_captured_mediaitems.path_full) for _captured_mediaitems in captured_mediaitems]

    context = AnimationContext(animation_images)
    steps = []
    steps.append(AddPredefinedImagesStep(config.merge_definition))
    steps.append(PostPredefinedImagesStep(config.merge_definition))
    steps.append(AlignSizesStep(canvas_size))
    pipeline = Pipeline[AnimationContext](*steps)
    pipeline(context)

    sequence_images = context.images

    ## create mediaitem
    sequence_images[0].save(
        mediaitem.path_original,
        format="gif",
        save_all=True,
        append_images=sequence_images[1:] if len(sequence_images) > 1 else [],
        optimize=True,
        # duration per frame in milliseconds. integer=all frames same, list/tuple individual.
        duration=[definition.duration for definition in config.merge_definition],
        loop=0,  # loop forever
    )

    # create scaled versions (unprocessed and processed are same here for now
    tms = time.time()
    mediaitem.create_fileset_unprocessed()
    mediaitem.copy_fileset_processed()
    logger.info(f"-- process time: {round((time.time() - tms), 2)}s to create scaled versions")


def process_and_generate_wigglegram(captured_mediaitems: list[MediaItem], mediaitem: MediaItem):
    # get config from mediaitem, that is passed as json dict (model_dump) along with it
    config = MulticameraProcessing(**mediaitem._config)

    ## prepare: create canvas
    canvas_size = (config.canvas_width, config.canvas_height)

    ## stage: merge captured images and predefined to one image with transparency
    multicamera_images: list[Image.Image] = [Image.open(_captured_mediaitems.path_full) for _captured_mediaitems in captured_mediaitems]

    context = MulticameraContext(multicamera_images)
    steps = []
    steps.append(AlignSizesStep(canvas_size))
    pipeline = Pipeline[MulticameraContext](*steps)
    pipeline(context)

    sequence_images = context.images

    ## create mediaitem
    sequence_images[0].save(
        mediaitem.path_original,
        format="gif",
        save_all=True,
        append_images=sequence_images[1:] if len(sequence_images) > 1 else [],
        optimize=True,
        # duration per frame in milliseconds. integer=all frames same, list/tuple individual.
        duration=125,
        loop=0,  # loop forever
    )

    # create scaled versions (unprocessed and processed are same here for now
    tms = time.time()
    mediaitem.create_fileset_unprocessed()
    mediaitem.copy_fileset_processed()
    logger.info(f"-- process time: {round((time.time() - tms), 2)}s to create scaled versions")


def get_filter_preview(mediaitem: MediaItem, filter: str = None) -> io.BytesIO:
    # check for type. only specific types can have a filter applied by user
    if mediaitem.media_type not in (MediaItemTypes.image,):
        raise ValueError(f"Filter can't be applied for media_type={mediaitem.media_type}!")

    image = Image.open(mediaitem.path_thumbnail_unprocessed)
    context = ImageContext(image)
    steps = []

    if filter and filter != "original":
        steps.append(Pilgram2Step(filter))

    # setup pipeline.
    pipeline = Pipeline[ImageContext](*steps)

    # execute pipeline
    pipeline(context)

    # get result
    manipulated_image = context.image

    if manipulated_image.mode == "P":  # convert GIF palette to RGB so it can be stored as jpeg
        manipulated_image = manipulated_image.convert("RGB")

    buffer_preview_pipeline_applied = io.BytesIO()
    manipulated_image.save(buffer_preview_pipeline_applied, format="jpeg", quality=appconfig.mediaprocessing.THUMBNAIL_STILL_QUALITY, optimize=False)

    return buffer_preview_pipeline_applied
