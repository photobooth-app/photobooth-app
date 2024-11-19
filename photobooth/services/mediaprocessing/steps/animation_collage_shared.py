from PIL import Image

from ....utils.exceptions import PipelineError
from ....utils.helper import get_user_file
from ...config.models.models import AnimationMergeDefinition, CollageMergeDefinition
from ..context import AnimationContext, CollageContext, ImageContext
from ..pipeline import NextStep, Pipeline
from .image import Pilgram2Step


class AddPredefinedImagesStep:
    def __init__(self, merge_definition: list[CollageMergeDefinition] | list[AnimationMergeDefinition]) -> None:
        self.merge_definition = merge_definition

    def __call__(self, context: CollageContext | AnimationContext, next_step: NextStep) -> None:
        for idx, _definition in enumerate(self.merge_definition):
            assert hasattr(_definition, "predefined_image")

            if _definition.predefined_image:
                try:
                    predefined_image = Image.open(get_user_file(_definition.predefined_image))
                    context.images.insert(idx, predefined_image)
                except FileNotFoundError as exc:
                    raise PipelineError(f"error getting predefined file {exc}") from exc

        next_step(context)

    def __repr__(self) -> str:
        return self.__class__.__name__


class PostPredefinedImagesStep:
    """
    captures are postprocessed during capture, predefined not.
    the mergedefinition allows for pilgram2 filter to apply, so we need to apply these here.
    """

    def __init__(self, merge_definition: list[CollageMergeDefinition] | list[AnimationMergeDefinition]) -> None:
        self.merge_definition = merge_definition

    def __call__(self, context: CollageContext | AnimationContext, next_step: NextStep) -> None:
        if len(self.merge_definition) != len(context.images):
            raise RuntimeError("error processing, wrong number of images")

        for idx, image in enumerate(context.images):
            assert hasattr(self.merge_definition[idx], "predefined_image")

            if self.merge_definition[idx].predefined_image:
                sub_context = ImageContext(image)
                sub_steps = []

                filter = self.merge_definition[idx].filter
                if filter and filter != "original":
                    sub_steps.append(Pilgram2Step(filter))

                sub_pipeline = Pipeline[ImageContext](*sub_steps)
                sub_pipeline(sub_context)

                context.images[idx] = sub_context.image

        next_step(context)

    def __repr__(self) -> str:
        return self.__class__.__name__
