from __future__ import annotations

import logging
import shutil
import time
import traceback
from pathlib import Path

from PIL import Image, ImageOps

from ...appconfig import appconfig
from ...database.models import Mediaitem
from ..config.groups.actions import AnimationProcessing, CollageProcessing, MulticameraProcessing, VideoProcessing
from ..config.models.models import SinglePictureDefinition
from .context import AnimationContext, CollageContext, ImageContext, MulticameraContext, VideoContext
from .pipeline import NextStep, Pipeline
from .steps.animation import AlignSizesStep
from .steps.animation_collage_shared import AddPredefinedImagesStep, PostPredefinedImagesStep
from .steps.collage import MergeCollageStep
from .steps.image import FillBackgroundStep, ImageFrameStep, ImageMountStep, PluginFilterStep, RemoveChromakeyStep, TextStep
from .steps.video import BoomerangStep

logger = logging.getLogger(__name__)


def process_image_inner(file_in: Path, config: SinglePictureDefinition, preview: bool):
    """
    Unified handling of images that are just one single capture: 1pictaken (singleimages) and stills that are used in collages or animation
    Since config is different and also can depend on the current number of the image in the capture sequence,
    the config has to be determined externally.
    """

    image = Image.open(file_in)
    ImageOps.exif_transpose(image, in_place=True)  # to correct for any orientation set.

    context = ImageContext(image, preview)
    steps = []

    # assemble pipeline
    if appconfig.mediaprocessing.removechromakey_enable:
        steps.append(RemoveChromakeyStep(appconfig.mediaprocessing.removechromakey_keycolor, appconfig.mediaprocessing.removechromakey_tolerance))

    if config.image_filter:
        steps.append(PluginFilterStep(config.image_filter))

    if config.img_background_enable:
        if not config.img_background_file:
            raise ValueError("image background enabled, but no file given")
        steps.append(ImageMountStep(config.img_background_file))

    if config.fill_background_enable:
        steps.append(FillBackgroundStep(config.fill_background_color))

    if config.img_frame_enable:
        if not config.img_frame_file:
            raise ValueError("image frame enabled, but no file given")
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
    manipulated_image = manipulated_image.convert("RGB") if manipulated_image.mode in ("RGBA", "P") else manipulated_image

    return manipulated_image


def process_image_collageimage_animationimage(file_in: Path, mediaitem: Mediaitem):
    manipulated_image = process_image_inner(file_in, SinglePictureDefinition(**mediaitem.pipeline_config), preview=False)

    # finish up creating mediafiles representants.
    ## final: save full result and create scaled versions
    # complete processed version (unprocessed and processed are different here)
    manipulated_image.save(mediaitem.processed, format="jpeg", quality=appconfig.mediaprocessing.HIRES_STILL_QUALITY, optimize=True)

    return mediaitem


def process_video(video_in: Path, mediaitem: Mediaitem):
    # get config from mediaitem, that is passed as json dict (model_dump) along with it
    config = VideoProcessing(**mediaitem.pipeline_config)

    context = VideoContext(video_in)
    steps = []

    if config.boomerang:
        steps.append(BoomerangStep())

    # setup pipeline.
    pipeline = Pipeline[VideoContext](*steps)

    # execute pipeline
    pipeline(context)

    # get result
    assert context.video_processed
    video_processed = context.video_processed

    # create final video
    shutil.move(video_processed, mediaitem.unprocessed)
    # complete processed version (unprocessed and processed are same here for this one)
    shutil.copy2(mediaitem.unprocessed, mediaitem.processed)


def process_and_generate_collage(files_in: list[Path], mediaitem: Mediaitem):
    # get config from mediaitem, that is passed as json dict (model_dump) along with it
    config = CollageProcessing(**mediaitem.pipeline_config)

    ## prepare: create canvas and input images
    canvas_size = (config.canvas_width, config.canvas_height)
    canvas = Image.new("RGBA", canvas_size, color=None)
    collage_images: list[Image.Image] = [Image.open(image_in) for image_in in files_in]

    context = CollageContext(canvas, collage_images)
    steps = []
    steps.append(AddPredefinedImagesStep(config.merge_definition))
    steps.append(PostPredefinedImagesStep(config.merge_definition))
    steps.append(MergeCollageStep(config.merge_definition))
    pipeline = Pipeline[CollageContext](*steps)
    pipeline(context)

    canvas = context.canvas

    ## phase 2
    context = ImageContext(canvas, False)
    steps = []

    # assemble pipeline

    if config.canvas_img_background_enable:
        if not config.canvas_img_background_file:
            raise ValueError("image background enabled, but no file given")
        steps.append(ImageMountStep(config.canvas_img_background_file))

    if config.canvas_fill_background_enable:
        steps.append(FillBackgroundStep(config.canvas_fill_background_color))

    if config.canvas_img_front_enable:
        if not config.canvas_img_front_file:
            raise ValueError("image frame enabled, but no file given")
        steps.append(ImageMountStep(config.canvas_img_front_file, reverse=True))

    if config.canvas_texts_enable:
        steps.append(TextStep(config.canvas_texts))

    pipeline = Pipeline[ImageContext](*steps)
    pipeline(context)

    canvas = context.image

    ## create mediaitem
    canvas = canvas.convert("RGB") if canvas.mode in ("RGBA", "P") else canvas
    canvas.save(mediaitem.unprocessed, format="jpeg", quality=appconfig.mediaprocessing.HIRES_STILL_QUALITY, optimize=True)

    # complete processed version (unprocessed and processed are same here for this one)
    shutil.copy2(mediaitem.unprocessed, mediaitem.processed)


def process_and_generate_animation(files_in: list[Path], mediaitem: Mediaitem):
    # get config from mediaitem, that is passed as json dict (model_dump) along with it
    config = AnimationProcessing(**mediaitem.pipeline_config)

    ## prepare: create canvas
    canvas_size = (config.canvas_width, config.canvas_height)

    ## stage: merge captured images and predefined to one image with transparency
    animation_images: list[Image.Image] = [Image.open(image_in) for image_in in files_in]

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
        mediaitem.unprocessed,
        format="gif",
        save_all=True,
        append_images=sequence_images[1:] if len(sequence_images) > 1 else [],
        optimize=True,
        # duration per frame in milliseconds. integer=all frames same, list/tuple individual.
        duration=[definition.duration for definition in config.merge_definition],
        loop=0,  # loop forever
    )

    # complete processed version (unprocessed and processed are same here for this one)
    shutil.copy2(mediaitem.unprocessed, mediaitem.processed)


def process_and_generate_wigglegram(files_in: list[Path], mediaitem: Mediaitem):
    # get config from mediaitem, that is passed as json dict (model_dump) along with it
    config = MulticameraProcessing(**mediaitem.pipeline_config)

    ## prepare: create canvas
    canvas_size = (config.canvas_width, config.canvas_height)

    ## stage: merge captured images and predefined to one image with transparency
    multicamera_images: list[Image.Image] = [Image.open(image_in) for image_in in files_in]

    context = MulticameraContext(multicamera_images)
    steps = []
    steps.append(AlignSizesStep(canvas_size))
    pipeline = Pipeline[MulticameraContext](*steps)
    pipeline(context)

    # sequence like 1-2-3-4-3-2-restart
    sequence_images = context.images
    sequence_images = sequence_images + list(reversed(sequence_images[1 : len(sequence_images) - 1]))  # add reversed list except first+last item

    ## create mediaitem
    sequence_images[0].save(
        mediaitem.unprocessed,
        format="gif",
        save_all=True,
        append_images=sequence_images[1:] if len(sequence_images) > 1 else [],
        optimize=True,
        # duration per frame in milliseconds. integer=all frames same, list/tuple individual.
        duration=125,
        loop=0,  # loop forever
    )

    # unprocessed and processed are same here for now
    shutil.copy2(mediaitem.unprocessed, mediaitem.processed)
