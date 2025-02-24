import logging
from enum import Enum

import pilgram2
from PIL import Image

# from photobooth.services.mediaprocessing.steps.image import PluginFilters
from .. import hookimpl
from ..base_plugin import BasePlugin
from . import config

logger = logging.getLogger(__name__)


class FilterPilgram2(BasePlugin[config.FilterPilgram2Config]):
    def __init__(self):
        super().__init__()

        self._config: config.FilterPilgram2Config = config.FilterPilgram2Config()

    @hookimpl
    def mp_avail_filter(self) -> list[str]:
        return [str(e) for e in config.PilgramFilter]

    @hookimpl
    def mp_userselectable_filter(self) -> list[str]:
        if self._config.add_userselectable_filter:
            return [str(e) for e in self._config.userselectable_filter]
        else:
            return []

    @hookimpl
    def mp_filter_pipeline_step(self, image: Image.Image, plugin_filter: Enum, preview: bool) -> Image.Image | None:
        (plugin_filter_enum_name, filter_value) = str(plugin_filter.value).split(".", 2)
        if hasattr(config, plugin_filter_enum_name):  # if true, this filter is requested.
            return self.do_filter(image, config.PilgramFilter(filter_value))

    def do_filter(self, image: Image.Image, config: config.PilgramFilter) -> Image.Image:
        try:
            pilgram2_filter_fun = getattr(pilgram2, config.value)
        except Exception as exc:
            raise ValueError(f"pilgram2 filter {config} does not exist") from exc

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
