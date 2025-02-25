import logging
from typing import cast, get_args

import pilgram2
from PIL import Image

from .. import hookimpl
from ..base_plugin import BaseFilter
from .config import FilterPilgram2Config, available_filter

logger = logging.getLogger(__name__)


class FilterPilgram2(BaseFilter[FilterPilgram2Config]):
    def __init__(self):
        super().__init__()

        self._config: FilterPilgram2Config = FilterPilgram2Config()

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
            pilgram2_filter_fun = getattr(pilgram2, filter)
        except Exception as exc:
            raise ValueError(f"pilgram2 filter {filter} does not exist") from exc

        # apply filter
        filtered_image: Image.Image = pilgram2_filter_fun(image.copy())

        if image.mode == "RGBA":
            # remark: "P" mode is palette (like GIF) that could have a transparent color defined also
            # since we do not use transparent GIFs currently we can ignore here.
            # P would not have an alphachannel but only a transparent color defined.
            logger.debug("need to convert to rgba and readd transparency mask to filtered image")
            # get alpha from original image
            a = image.getchannel("A")
            # get rgb from filtered image
            r, g, b = filtered_image.split()
            # and merge both
            filtered_transparent_image = Image.merge(image.mode, (r, g, b, a))

            filtered_image = filtered_transparent_image
            del filtered_transparent_image

        return filtered_image
