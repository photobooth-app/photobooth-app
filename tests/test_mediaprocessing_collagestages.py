"""
Testing Mediaprocessing collage
"""
import logging

import pytest
from PIL import Image

import photobooth.services.mediaprocessing.collage_pipelinestages as collage_stages
from photobooth.services.config.groups.mediaprocessing import CollageMergeDefinition

logger = logging.getLogger(name=None)


def test_collage_stage():
    canvas = Image.new("RGBA", (1500, 1500), color=None)
    captured_images = [
        Image.open("tests/assets/input.jpg"),
        Image.open("tests/assets/input.jpg"),
        Image.open("tests/assets/input.jpg"),
    ]
    collage_merge_definition = [
        CollageMergeDefinition(rotate=5),
        CollageMergeDefinition(pos_x=800, rotate=-5),
        CollageMergeDefinition(pos_y=800),
    ]
    stage_output = collage_stages.merge_collage_stage(canvas, captured_images, collage_merge_definition)

    assert canvas.mode == "RGBA"
    assert canvas.mode == stage_output.mode
    assert canvas.size == stage_output.size
    assert canvas is stage_output  # actually we merged all on canvas which is also output


def test_collage_stage_definition_not_matching_with_no_captured():
    # 2 captures vs. 3 required per definition
    canvas = Image.new("RGBA", (1500, 1500), color=None)
    captured_images = [
        Image.open("tests/assets/input.jpg"),
        Image.open("tests/assets/input.jpg"),
    ]
    collage_merge_definition = [
        CollageMergeDefinition(rotate=5),
        CollageMergeDefinition(pos_x=800, rotate=-5),
        CollageMergeDefinition(pos_y=800),
    ]
    with pytest.raises(AssertionError):
        _ = collage_stages.merge_collage_stage(canvas, captured_images, collage_merge_definition)
