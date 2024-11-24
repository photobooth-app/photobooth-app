import logging

import pytest
from PIL import Image

from photobooth.services.config.groups.actions import AnimationMergeDefinition, CollageMergeDefinition
from photobooth.services.config.models.models import PilgramFilter
from photobooth.services.mediaprocessing.context import AnimationContext, CollageContext
from photobooth.services.mediaprocessing.pipeline import Pipeline
from photobooth.services.mediaprocessing.steps.animation_collage_shared import AddPredefinedImagesStep, PostPredefinedImagesStep

logger = logging.getLogger(name=None)


def test_collage_shared():
    canvas = Image.new("RGBA", (1500, 1500), color=None)
    images = [
        Image.open("tests/assets/input.jpg"),
    ]
    merge_definition = [
        CollageMergeDefinition(predefined_image="tests/assets/input.jpg", filter=PilgramFilter._1977),
        CollageMergeDefinition(filter=PilgramFilter._1977),
    ]

    context = CollageContext(canvas, images)
    steps = [
        AddPredefinedImagesStep(merge_definition),
        PostPredefinedImagesStep(merge_definition),
    ]
    pipeline = Pipeline[CollageContext](*steps)
    pipeline(context)


def test_animation_shared():
    images = [
        Image.open("tests/assets/input.jpg"),
    ]
    merge_definition = [
        AnimationMergeDefinition(predefined_image="tests/assets/input.jpg", filter=PilgramFilter._1977),
        AnimationMergeDefinition(filter=PilgramFilter._1977),
    ]

    context = AnimationContext(images)
    steps = [
        AddPredefinedImagesStep(merge_definition),
        PostPredefinedImagesStep(merge_definition),
    ]
    pipeline = Pipeline[AnimationContext](*steps)
    pipeline(context)


def test_animation_shared_wrongnumbers_runtime():
    images = [
        Image.open("tests/assets/input.jpg"),
        Image.open("tests/assets/input.jpg"),
    ]
    merge_definition = [
        # we have two captured images and two definitions but one is already a predefined. thats bad because we should have only one captured
        AnimationMergeDefinition(predefined_image="tests/assets/input.jpg", filter=PilgramFilter._1977),
        AnimationMergeDefinition(filter=PilgramFilter._1977),
    ]

    context = AnimationContext(images)
    steps = [
        AddPredefinedImagesStep(merge_definition),
        PostPredefinedImagesStep(merge_definition),
    ]
    pipeline = Pipeline[AnimationContext](*steps)

    with pytest.raises(RuntimeError):
        pipeline(context)