import hashlib
import logging
import time
from pathlib import Path
from threading import BoundedSemaphore, Lock

from PIL import Image, ImageOps

from ... import CACHE_PATH
from ...models.genericstats import GenericStats, SubStats
from .. import hookimpl
from ..base_plugin import BaseFilter
from .config import AiStyle, FilterAiRestylerConfig
from .providers import create_provider
from .providers.base import encode_jpeg

logger = logging.getLogger(__name__)

SHIPPED_PREVIEWS = Path(__file__).parent / "previews"


class FilterAiRestyler(BaseFilter[FilterAiRestylerConfig]):
    def __init__(self):
        super().__init__()

        self._config: FilterAiRestylerConfig = FilterAiRestylerConfig()

        self._cache_dir = Path(CACHE_PATH, "ai_restyler")
        self._semaphore: BoundedSemaphore | None = None
        self._semaphore_size = 0
        self._lock = Lock()

        self._stats_requests = 0
        self._stats_cache_hits = 0
        self._stats_errors = 0
        self._stats_last_duration = 0.0

    @hookimpl
    def mp_avail_filter(self) -> list[str]:
        # always list all styles, so actions referencing a style stay valid if the plugin is disabled.
        return [self.unify(style.id) for style in self._config.styles]

    @hookimpl
    def mp_userselectable_filter(self) -> list[str]:
        if self._config.common.enabled and self._config.common.add_userselectable_filter:
            return [self.unify(style.id) for style in self._config.styles if style.userselectable]
        else:
            return []

    @hookimpl
    def mp_filter_pipeline_step(self, image: Image.Image, plugin_filter: str, preview: bool) -> Image.Image | None:
        style_id = self.deunify(plugin_filter)

        if not style_id:
            return None

        style = self._config.get_style(style_id)

        if preview:
            return self.do_preview(image, style)

        if not self._config.common.enabled:
            raise RuntimeError("AI style plugin is disabled, enable it in the plugin configuration to apply AI styles")

        return self.do_filter(image, style)

    @hookimpl
    def get_stats(self) -> GenericStats | None:
        if not self._config.common.enabled:
            return None

        return GenericStats(
            id="hook-plugin-filter-ai-restyler",
            name="AI Restyler",
            stats=[
                SubStats("provider", self._config.provider.provider_type),
                SubStats("requests", self._stats_requests),
                SubStats("cache hits", self._stats_cache_hits),
                SubStats("errors", self._stats_errors),
                SubStats("last request duration", self._stats_last_duration, decimals=1, unit="s"),
            ],
        )

    def do_preview(self, image: Image.Image, style: AiStyle) -> Image.Image:
        """previews are used to display the filter selection. AI requests are slow and cost money, so show a sample of the style instead."""

        preview_image = style.preview_image or SHIPPED_PREVIEWS / f"{style.id}.jpg"

        if preview_image.is_file():
            try:
                with Image.open(preview_image) as sample:
                    if sample.width * image.height > sample.height * image.width:
                        width = max(1, round(sample.height * image.width / image.height))
                        left = (sample.width - width) // 2
                        box = (left, 0, left + width, sample.height)
                    else:
                        height = max(1, round(sample.width * image.height / image.width))
                        top = (sample.height - height) // 2
                        box = (0, top, sample.width, top + height)

                    cropped = sample.crop(box)
                    return cropped if cropped.mode == "RGB" else cropped.convert("RGB")
            except Exception as exc:
                logger.warning(f"cannot load preview image {preview_image} of style {style.id}: {exc}")

        return image.copy()

    def do_filter(self, image: Image.Image, style: AiStyle) -> Image.Image:
        provider = create_provider(self._config.provider)
        prompt = self._config.common.prompt_template.replace("{style}", style.prompt)

        input_image = image.convert("RGB")
        input_image.thumbnail((self._config.common.max_input_size, self._config.common.max_input_size), Image.Resampling.BICUBIC)
        input_jpeg = encode_jpeg(input_image)

        cache_key = hashlib.sha256(
            b"\0".join([input_jpeg, prompt.encode(), style.negative_prompt.encode(), provider.cache_identifier.encode()])
        ).hexdigest()

        result = self._cache_get(cache_key)
        if result is not None:
            self._stats_cache_hits += 1
            logger.info(f"AI style {style.id} result loaded from cache")
        else:
            start = time.monotonic()
            self._stats_requests += 1
            try:
                with self._get_semaphore():
                    result = provider.restyle(input_jpeg, prompt, style.negative_prompt)
            except Exception:
                self._stats_errors += 1
                raise
            finally:
                self._stats_last_duration = time.monotonic() - start

            logger.info(f"AI style {style.id} applied by {self._config.provider.provider_type} in {self._stats_last_duration:.1f}s")
            self._cache_put(cache_key, result)

        # the result needs to match the original size so frames, collages and other pipeline steps still fit.
        filtered_image = ImageOps.fit(result.convert("RGB"), image.size, Image.Resampling.BICUBIC)

        if image.mode == "RGBA":
            filtered_image.putalpha(image.getchannel("A"))

        return filtered_image

    def _get_semaphore(self) -> BoundedSemaphore:
        with self._lock:
            if self._semaphore is None or self._semaphore_size != self._config.common.max_concurrent_requests:
                self._semaphore_size = self._config.common.max_concurrent_requests
                self._semaphore = BoundedSemaphore(self._semaphore_size)
            return self._semaphore

    def _cache_get(self, key: str) -> Image.Image | None:
        if self._config.common.cache_max_entries == 0:
            return None

        cache_file = self._cache_dir / f"{key}.jpg"
        try:
            with Image.open(cache_file) as cached:
                cached.load()
                cache_file.touch()  # lru
                return cached.copy()
        except FileNotFoundError:
            return None
        except Exception as exc:
            logger.warning(f"cannot read cached AI style result {cache_file}: {exc}")
            return None

    def _cache_put(self, key: str, image: Image.Image):
        if self._config.common.cache_max_entries == 0:
            return

        try:
            self._cache_dir.mkdir(parents=True, exist_ok=True)
            (self._cache_dir / f"{key}.jpg").write_bytes(encode_jpeg(image, quality=95))

            entries = sorted(self._cache_dir.glob("*.jpg"), key=lambda p: p.stat().st_mtime, reverse=True)
            for old in entries[self._config.common.cache_max_entries :]:
                old.unlink(missing_ok=True)
        except Exception as exc:
            logger.warning(f"cannot cache AI style result: {exc}")
