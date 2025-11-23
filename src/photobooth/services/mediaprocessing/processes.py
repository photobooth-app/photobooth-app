from __future__ import annotations

import logging
import shutil
import traceback
from pathlib import Path

from PIL import Image, ImageOps

from ...appconfig import appconfig
from ...database.models import Mediaitem
from ...utils.media_encode import encode
from ...utils.metrics_timer import MetricsTimer
from ..config.groups.actions import AnimationProcessing, CollageProcessing, MulticameraProcessing, SingleImageProcessing, VideoProcessing
from .context import AnimationContext, CollageContext, ImageContext, MulticameraContext, VideoContext
from .pipeline import NextStep, Pipeline, PipelineStep
from .steps.animation import AlignSizesStep
from .steps.animation_collage_shared import AddPredefinedImagesStep, PostPredefinedImagesStep
from .steps.collage import MergeCollageStep
from .steps.image import FillBackgroundStep, ImageFrameStep, ImageMountStep, PluginFilterStep, RemovebgStep, TextStep
from .steps.multicamera import AlignAsPerCalibrationStep
from .steps.video import BoomerangStep

logger = logging.getLogger(__name__)


def process_image_inner(file_in: Path, config: SingleImageProcessing, preview: bool):
    """
    Unified handling of images that are just one single capture: 1pictaken (singleimages) and stills that are used in collages or animation
    Since config is different and also can depend on the current number of the image in the capture sequence,
    the config has to be determined externally.

    Preview is true if we need a quick generation of a preview for filter selection. Used to save CPU
    """

    image = Image.open(file_in)
    ImageOps.exif_transpose(image, in_place=True)  # to correct for any orientation set.

    context = ImageContext(image, preview)
    steps = []

    # assemble pipeline
    if config.remove_background and not preview:
        steps.append(RemovebgStep(model_name=appconfig.mediaprocessing.remove_background_model))

    if config.img_background_enable:
        if not config.img_background_file:
            raise ValueError("image background enabled, but no file given")
        steps.append(ImageMountStep(config.img_background_file))

    if config.fill_background_enable:
        steps.append(FillBackgroundStep(config.fill_background_color))

    if config.image_filter:
        steps.append(PluginFilterStep(config.image_filter))

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
    with MetricsTimer(process_image_inner.__name__):
        pipeline(context, _error_handler)

    # get result
    manipulated_image = context.image
    manipulated_image = manipulated_image.convert("RGB") if manipulated_image.mode in ("RGBA", "P") else manipulated_image

    return manipulated_image


def process_phase1images(file_in: Path, mediaitem: Mediaitem):
    manipulated_image = process_image_inner(file_in, SingleImageProcessing(**mediaitem.pipeline_config), preview=False)

    ## final: save full result and create scaled versions
    # complete processed version (unprocessed and processed are different here)
    encode([manipulated_image], mediaitem.processed)

    return mediaitem


def process_video(video_in: Path, mediaitem: Mediaitem):
    # get config from mediaitem, that is passed as json dict (model_dump) along with it
    config = VideoProcessing(**mediaitem.pipeline_config)

    context = VideoContext(video_in)
    steps = []

    if config.boomerang:
        steps.append(BoomerangStep(config.boomerang_speed))

    # setup pipeline.
    pipeline = Pipeline[VideoContext](*steps)
    with MetricsTimer(process_video.__name__):
        pipeline(context)

    # get result
    video_processed = context.video_processed if context.video_processed else context.video_in  # if pipeline was empty, use input as output

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
    steps_phase1: list[PipelineStep[CollageContext]] = []
    steps_phase1.append(AddPredefinedImagesStep(config.merge_definition))
    steps_phase1.append(PostPredefinedImagesStep(config.merge_definition))
    steps_phase1.append(MergeCollageStep(config.merge_definition))
    pipeline = Pipeline[CollageContext](*steps_phase1)
    pipeline(context)

    canvas = context.canvas

    ## phase 2
    context = ImageContext(canvas, False)
    steps_phase2: list[PipelineStep[ImageContext]] = []

    # assemble pipeline
    if config.canvas_img_background_enable:
        if not config.canvas_img_background_file:
            raise ValueError("image background enabled, but no file given")
        steps_phase2.append(ImageMountStep(config.canvas_img_background_file))

    if config.canvas_fill_background_enable:
        steps_phase2.append(FillBackgroundStep(config.canvas_fill_background_color))

    if config.canvas_img_front_enable:
        if not config.canvas_img_front_file:
            raise ValueError("image frame enabled, but no file given")
        steps_phase2.append(ImageMountStep(config.canvas_img_front_file, reverse=True))

    if config.canvas_texts_enable:
        steps_phase2.append(TextStep(config.canvas_texts))

    pipeline = Pipeline[ImageContext](*steps_phase2)
    with MetricsTimer(process_and_generate_collage.__name__):
        pipeline(context)

    canvas = context.image

    ## create mediaitem
    canvas = canvas.convert("RGB") if canvas.mode in ("RGBA", "P") else canvas
    encode([canvas], mediaitem.unprocessed)
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
    with MetricsTimer(process_and_generate_animation.__name__):
        pipeline(context)

    ## create mediaitem
    encode(context.images, mediaitem.unprocessed, durations=[definition.duration for definition in config.merge_definition])
    # complete processed version (unprocessed and processed are same here for this one)
    shutil.copy2(mediaitem.unprocessed, mediaitem.processed)


def process_wigglegram_inner(files_in: list[Path], config: MulticameraProcessing, preview: bool) -> list[Image.Image]:
    ## stage: merge captured images and predefined to one image with transparency
    multicamera_images: list[Image.Image] = [Image.open(image_in) for image_in in files_in]

    context = MulticameraContext(multicamera_images)
    steps = []
    steps.append(AlignAsPerCalibrationStep())
    # steps.append(AutoPivotPointStep())
    # steps.append(OffsetPerOpticalFlowStep())
    # steps.append(CropCommonAreaStep())

    pipeline = Pipeline[MulticameraContext](*steps)
    with MetricsTimer(process_and_generate_wigglegram.__name__):
        pipeline(context)

    return context.images


def process_and_generate_wigglegram(files_in: list[Path], mediaitem: Mediaitem):
    # get config from mediaitem, that is passed as json dict (model_dump) along with it
    config = MulticameraProcessing(**mediaitem.pipeline_config)
    manipulated_image = process_wigglegram_inner(files_in, config, preview=False)

    ## finalize, create sequence and save
    # sequence like 1-2-3-4-3-2-restart
    sequence_images = manipulated_image
    sequence_images = sequence_images + list(reversed(sequence_images[1 : len(sequence_images) - 1]))  # add reversed list except first+last item
    encode(sequence_images, mediaitem.unprocessed, durations=config.duration)
    # unprocessed and processed are same here for now
    shutil.copy2(mediaitem.unprocessed, mediaitem.processed)

    return mediaitem
