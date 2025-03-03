import logging
from typing import cast, get_args

from PIL import Image

from photobooth.plugins.filter_stable.runner.getimg import GetImgAIFilter

from .. import hookimpl
from ..base_plugin import BaseFilter
from .config import FilterStableConfig, available_filter
from .sdpresets import filterpresets_sd

logger = logging.getLogger(__name__)


class FilterStable(BaseFilter[FilterStableConfig]):
    def __init__(self):
        super().__init__()

        self._config: FilterStableConfig = FilterStableConfig()

    @hookimpl
    def mp_avail_filter(self) -> list[str]:
        return [self.unify(f) for f in get_args(available_filter)]

    @hookimpl
    def mp_userselectable_filter(self) -> list[str]:
        if self._config.add_userselectable_filter:
            return [self.unify(f) for f in self._config.userselectable_filter]
        else:
            return []

    @hookimpl
    def mp_filter_pipeline_step(self, image: Image.Image, plugin_filter: str, preview: bool) -> Image.Image | None:
        filter = self.deunify(plugin_filter)

        if filter:  # if anything, then filter, else for None this plugin is not requested, leave.
            return self.do_filter(image, cast(available_filter, filter))

    def do_filter(self, image: Image.Image, filter: available_filter) -> Image.Image:
        try:
            filter_runner = GetImgAIFilter(api_key=self._config.getimg_api_key)

        except Exception as exc:
            raise RuntimeError(f"error processing the filter {filter}") from exc

        # get preset
        try:
            filter_preset = getattr(filterpresets_sd, filter)
        except Exception as exc:
            raise ValueError(f"stable filter preset {filter} does not exist") from exc

        # apply filter
        filtered_image: Image.Image = filter_runner.run(filter_preset, image)

        return filtered_image
