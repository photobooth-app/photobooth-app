import base64
import io
import json
import os
from pathlib import Path
from typing import cast

import pytest
import simplejpeg
from PIL import Image
from pydantic import HttpUrl, SecretStr, ValidationError
from pytest_httpserver import HTTPServer

from photobooth.plugins.filter_ai_restyler.config import (
    AiStyle,
    ComfyUIProviderConfig,
    FalProviderConfig,
    FilterAiRestylerConfig,
    ReplicateProviderConfig,
)
from photobooth.plugins.filter_ai_restyler.filter_ai_restyler import SHIPPED_PREVIEWS, FilterAiRestyler
from photobooth.plugins.filter_ai_restyler.providers.base import ProviderError, encode_jpeg
from photobooth.plugins.filter_ai_restyler.providers.comfyui import fill_placeholders

INPUT_SIZE = (400, 300)


def _jpeg(size=(256, 256), color=(255, 0, 0)) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", size, color).save(buffer, format="jpeg")
    return buffer.getvalue()


@pytest.fixture()
def plugin(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    # Never load local plugin settings, which may contain real API keys.
    monkeypatch.setitem(FilterAiRestylerConfig.model_config, "json_file", str(tmp_path / "nonexistent.json"))
    monkeypatch.setitem(FilterAiRestylerConfig.model_config, "env_file", None)
    for key in list(os.environ):
        if key.startswith("filter-ai-restyler-"):
            monkeypatch.delenv(key)
    p = FilterAiRestyler()
    p._config = FilterAiRestylerConfig()
    p._config.common.enabled = True
    p._cache_dir = tmp_path / "cache"
    yield p


@pytest.fixture()
def image():
    return Image.new("RGB", INPUT_SIZE, (0, 0, 255))


@pytest.fixture()
def input_jpegs(monkeypatch: pytest.MonkeyPatch):
    encoded_inputs: list[bytes] = []
    original_encode = simplejpeg.encode_jpeg

    def capture_encode(*args, **kwargs):
        jpeg = original_encode(*args, **kwargs)
        if kwargs.get("quality") == 90:
            encoded_inputs.append(jpeg)
        return jpeg

    monkeypatch.setattr(simplejpeg, "encode_jpeg", capture_encode)
    return encoded_inputs


def _setup_fal(plugin: FilterAiRestyler, httpserver: HTTPServer):
    plugin._config.provider = FalProviderConfig(api_key=SecretStr("testkey"), base_url=HttpUrl(httpserver.url_for("/")), model_id="fal-ai/test-model")
    result_uri = f"data:image/jpeg;base64,{base64.b64encode(_jpeg()).decode()}"
    httpserver.expect_request("/fal-ai/test-model", method="POST", headers={"Authorization": "Key testkey"}).respond_with_json(
        {"images": [{"url": result_uri}]}
    )


def test_unify_and_foreign_filter(plugin: FilterAiRestyler, image):
    assert "FilterAiRestyler.cartoon" in plugin.mp_avail_filter()
    assert plugin.mp_filter_pipeline_step(image, "FilterPilgram2._1977", preview=False) is None


def test_default_userselectable_styles_are_sorted_by_name(plugin: FilterAiRestyler):
    names = {plugin.unify(style.id): style.name for style in plugin._config.styles}
    selectable_names = [names[filter_id] for filter_id in plugin.mp_userselectable_filter()]

    assert selectable_names
    assert selectable_names == sorted(selectable_names, key=str.casefold)


def test_superhero_preset(plugin: FilterAiRestyler, image, httpserver: HTTPServer):
    _setup_fal(plugin, httpserver)
    filter_id = "FilterAiRestyler.superhero"

    assert filter_id in plugin.mp_avail_filter()
    assert filter_id in plugin.mp_userselectable_filter()
    result = plugin.mp_filter_pipeline_step(image, filter_id, preview=False)

    assert result and result.size == INPUT_SIZE
    prompt = httpserver.log[0][0].get_json()["prompt"]
    assert "superhero" in prompt
    assert "face uncovered and recognizable" in prompt


def test_superhero_preview(plugin: FilterAiRestyler, httpserver: HTTPServer):
    image = Image.new("RGB", (600, 400), "blue")
    result = plugin.mp_filter_pipeline_step(image, "FilterAiRestyler.superhero", preview=True)

    assert result is not None
    with Image.open(SHIPPED_PREVIEWS / "superhero.jpg") as sample:
        assert result.size == sample.size
        assert result.tobytes() == sample.tobytes()
    assert not httpserver.log


def test_disabled_plugin(plugin: FilterAiRestyler, image):
    plugin._config.common.enabled = False

    # avail filters remain so configured actions stay valid
    assert "FilterAiRestyler.cartoon" in plugin.mp_avail_filter()
    assert plugin.mp_userselectable_filter() == []
    with pytest.raises(RuntimeError):
        plugin.mp_filter_pipeline_step(image, "FilterAiRestyler.cartoon", preview=False)


def test_style_validation():
    with pytest.raises(ValidationError):
        AiStyle(id="has.dot", name="x", prompt="x")
    with pytest.raises(ValidationError):
        FilterAiRestylerConfig(styles=[AiStyle(id="a", name="a", prompt="a"), AiStyle(id="a", name="b", prompt="b")])


def test_preview_does_not_request(plugin: FilterAiRestyler, image, httpserver: HTTPServer):
    _setup_fal(plugin, httpserver)

    result = plugin.mp_filter_pipeline_step(image, "FilterAiRestyler.cartoon", preview=True)

    assert result is not None
    with Image.open(SHIPPED_PREVIEWS / "cartoon.jpg") as sample:
        expected = sample.crop((33, 0, 566, 400))
        assert result.size == expected.size
        assert result.tobytes() == expected.tobytes()
    assert len(httpserver.log) == 0


def test_preview_fallback(plugin: FilterAiRestyler, image):
    # styles without preview_image use the preview shipped with the plugin for the same id
    plugin._config.styles = [AiStyle(id="cartoon", name="c", prompt="c"), AiStyle(id="custom", name="x", prompt="x")]

    assert plugin.do_preview(image, plugin._config.styles[0]).tobytes() != image.tobytes()
    assert plugin.do_preview(image, plugin._config.styles[1]).tobytes() == image.tobytes()


def test_preview_sample_image(plugin: FilterAiRestyler, image, tmp_path: Path):
    sample = tmp_path / "sample.jpg"
    sample.write_bytes(_jpeg((100, 100), (0, 255, 0)))
    plugin._config.styles = [AiStyle(id="custom", name="Custom", prompt="custom", preview_image=sample)]

    result = plugin.mp_filter_pipeline_step(image, "FilterAiRestyler.custom", preview=True)

    assert result and result.size == (100, 75)
    assert cast(tuple, result.getpixel((50, 37)))[1] > 200


@pytest.mark.parametrize(
    ("mode", "input_size", "crop_box"),
    [
        ("RGB", (400, 300), (0, 12, 100, 87)),
        ("RGBA", (300, 400), (12, 0, 87, 100)),
        ("L", (10, 10), (0, 0, 100, 100)),
        ("RGB", (1000, 1), (0, 49, 100, 50)),
        ("RGB", (1, 1000), (49, 0, 50, 100)),
    ],
)
def test_preview_crops_without_resizing(
    plugin: FilterAiRestyler, tmp_path: Path, mode: str, input_size: tuple[int, int], crop_box: tuple[int, int, int, int]
):
    sample = Image.new("RGB", (100, 100))
    for x in range(sample.width):
        for y in range(sample.height):
            sample.putpixel((x, y), (x, y, 128))
    sample = sample.convert(mode)
    if mode == "RGBA":
        sample.putalpha(0)
    sample_path = tmp_path / "sample.png"
    sample.save(sample_path)
    style = AiStyle(id="custom", name="Custom", prompt="custom", preview_image=sample_path)

    result = plugin.do_preview(Image.new("RGB", input_size), style)
    expected = sample.crop(crop_box).convert("RGB")
    assert result.size == expected.size and result.mode == "RGB"
    assert result.tobytes() == expected.tobytes()


def test_fal_and_cache(plugin: FilterAiRestyler, image, httpserver: HTTPServer, input_jpegs: list[bytes]):
    _setup_fal(plugin, httpserver)
    plugin._config.common.max_input_size = 128

    result = plugin.mp_filter_pipeline_step(image, "FilterAiRestyler.cartoon", preview=False)
    assert result and result.size == INPUT_SIZE
    assert cast(tuple, result.getpixel((200, 150)))[0] > 200

    payload = httpserver.log[0][0].get_json()
    assert payload["image_url"].startswith("data:image/jpeg;base64,")
    assert "colorful 2D cartoon" in payload["prompt"]
    assert "clearly recognizable" in payload["prompt"]
    assert "gender presentation" in payload["prompt"]
    assert len(input_jpegs) == 1
    assert base64.b64decode(payload["image_url"].split(",", 1)[1]) == input_jpegs[0]
    with Image.open(io.BytesIO(input_jpegs[0])) as uploaded:
        assert uploaded.size == (128, 96)

    # second run is served from cache
    plugin.mp_filter_pipeline_step(image, "FilterAiRestyler.cartoon", preview=False)
    assert len(httpserver.log) == 1
    assert plugin._stats_cache_hits == 1
    assert len(input_jpegs) == 2
    assert input_jpegs[1] == input_jpegs[0]


@pytest.mark.parametrize(
    "source_image",
    [
        pytest.param(Image.new("RGB", (17, 13), (230, 20, 40)), id="rgb"),
        pytest.param(Image.new("RGBA", (17, 13), (230, 20, 40, 0)), id="rgba"),
        pytest.param(Image.new("L", (17, 13), 127), id="grayscale"),
    ],
)
def test_cache_write_without_pillow_encoder(plugin: FilterAiRestyler, source_image: Image.Image, monkeypatch: pytest.MonkeyPatch):
    def fail_pillow_save(*args, **kwargs):
        raise RuntimeError("Pillow encoder unavailable")

    monkeypatch.setattr(Image.Image, "save", fail_pillow_save)
    with Image.open(io.BytesIO(encode_jpeg(source_image))) as encoded:
        assert encoded.mode == "RGB" and encoded.size == source_image.size
        expected = cast(tuple, source_image.convert("RGB").getpixel((0, 0)))
        assert cast(tuple, encoded.getpixel((0, 0))) == pytest.approx(expected, abs=3)

    plugin._cache_put("cached", source_image)

    cached = plugin._cache_get("cached")
    assert cached is not None and cached.mode == "RGB" and cached.size == source_image.size
    expected = cast(tuple, source_image.convert("RGB").getpixel((0, 0)))
    assert cast(tuple, cached.getpixel((0, 0))) == pytest.approx(expected, abs=3)


def test_cache_encoder_error_is_logged(
    plugin: FilterAiRestyler, image: Image.Image, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
):
    def fail_encode(*args, **kwargs):
        raise ValueError("encoding failed")

    monkeypatch.setattr("simplejpeg.encode_jpeg", fail_encode)
    with caplog.at_level("WARNING"):
        plugin._cache_put("failed", image)

    assert "cannot cache AI style result: encoding failed" in caplog.text
    assert not (plugin._cache_dir / "failed.jpg").exists()


def test_rgba_alpha_preserved(plugin: FilterAiRestyler, httpserver: HTTPServer):
    _setup_fal(plugin, httpserver)
    image = Image.new("RGBA", INPUT_SIZE, (0, 0, 255, 0))
    image.paste((0, 0, 255, 255), (0, 0, 100, 100))

    result = plugin.mp_filter_pipeline_step(image, "FilterAiRestyler.cartoon", preview=False)

    assert result and result.mode == "RGBA" and result.size == INPUT_SIZE
    assert result.getchannel("A").getpixel((50, 50)) == 255
    assert result.getchannel("A").getpixel((300, 200)) == 0


def test_provider_error_raises(plugin: FilterAiRestyler, image, httpserver: HTTPServer):
    plugin._config.provider = FalProviderConfig(api_key=SecretStr("testkey"), base_url=HttpUrl(httpserver.url_for("/")), model_id="m")
    httpserver.expect_request("/m").respond_with_data("quota exceeded", status=402)

    with pytest.raises(Exception, match="402"):
        plugin.mp_filter_pipeline_step(image, "FilterAiRestyler.cartoon", preview=False)
    assert plugin._stats_errors == 1


@pytest.mark.parametrize("source", ["environment", "dotenv"])
def test_plugin_fixture_ignores_local_credentials(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, source: str):
    for key in list(os.environ):
        if key.startswith("filter-ai-restyler-"):
            monkeypatch.delenv(key)
    monkeypatch.chdir(tmp_path)
    settings = {
        "filter-ai-restyler-provider__provider_type": "replicate",
        "filter-ai-restyler-provider__api_key": "dummy-key",
    }
    if source == "environment":
        for key, value in settings.items():
            monkeypatch.setenv(key, value)
    else:
        (tmp_path / ".env.prod").write_text("".join(f"{key}={value}\n" for key, value in settings.items()))

    isolated_plugin = request.getfixturevalue("plugin")

    assert isolated_plugin._config.provider.api_key.get_secret_value() == ""


@pytest.mark.parametrize(
    ("provider", "message"),
    [
        (ReplicateProviderConfig(api_key=SecretStr("")), "Replicate API token is missing"),
        (FalProviderConfig(api_key=SecretStr("")), r"fal\.ai API key is missing"),
    ],
)
def test_missing_api_key_raises(
    plugin: FilterAiRestyler,
    image: Image.Image,
    monkeypatch: pytest.MonkeyPatch,
    provider: ReplicateProviderConfig | FalProviderConfig,
    message: str,
):
    def fail_request(*args, **kwargs):
        raise AssertionError("Unexpected provider request")

    monkeypatch.setattr("requests.post", fail_request)
    plugin._config.provider = provider
    with pytest.raises(ProviderError, match=message):
        plugin.mp_filter_pipeline_step(image, "FilterAiRestyler.cartoon", preview=False)


def test_replicate_polling(plugin: FilterAiRestyler, image, httpserver: HTTPServer, input_jpegs: list[bytes]):
    plugin._config.provider = ReplicateProviderConfig(api_key=SecretStr("token"), base_url=HttpUrl(httpserver.url_for("/v1")))
    httpserver.expect_request(
        "/v1/models/black-forest-labs/flux-kontext-pro/predictions", method="POST", headers={"Authorization": "Bearer token"}
    ).respond_with_json({"status": "processing", "urls": {"get": httpserver.url_for("/v1/predictions/abc"), "cancel": ""}})
    httpserver.expect_request("/v1/predictions/abc").respond_with_json({"status": "succeeded", "output": httpserver.url_for("/out.jpg")})
    httpserver.expect_request("/out.jpg").respond_with_data(_jpeg(), content_type="image/jpeg")

    result = plugin.mp_filter_pipeline_step(image, "FilterAiRestyler.vintage-1920s", preview=False)

    assert result and result.size == INPUT_SIZE
    payload = httpserver.log[0][0].get_json()["input"]
    assert payload["input_image"].startswith("data:image/jpeg;base64,")
    assert payload["aspect_ratio"] == "match_input_image"
    assert "1920s" in payload["prompt"] and "black-and-white" in payload["prompt"]
    assert "period-appropriate clothing and surroundings" in payload["prompt"]
    assert "preserving each person's face" in payload["prompt"]
    assert "gender presentation" in payload["prompt"]
    assert "facial hair" in payload["prompt"]
    assert "exact same position, scale and pose" in payload["prompt"]
    assert "{style}" not in payload["prompt"]
    assert len(input_jpegs) == 1
    assert base64.b64decode(payload["input_image"].split(",", 1)[1]) == input_jpegs[0]


def test_comfyui(plugin: FilterAiRestyler, image, httpserver: HTTPServer, tmp_path: Path, input_jpegs: list[bytes]):
    workflow = tmp_path / "workflow.json"
    workflow.write_text(
        json.dumps(
            {
                "1": {"class_type": "LoadImage", "inputs": {"image": "{{image}}"}},
                "2": {"class_type": "CLIPTextEncode", "inputs": {"text": "{{prompt}}"}},
                "3": {"class_type": "KSampler", "inputs": {"seed": "{{seed}}"}},
            }
        )
    )
    plugin._config.provider = ComfyUIProviderConfig(base_url=HttpUrl(httpserver.url_for("/")), workflow_file=workflow)

    httpserver.expect_request("/upload/image", method="POST").respond_with_json({"name": "up.jpg", "subfolder": "", "type": "input"})
    httpserver.expect_request("/prompt", method="POST").respond_with_json({"prompt_id": "pid"})
    httpserver.expect_request("/history/pid").respond_with_json(
        {
            "pid": {
                "status": {"status_str": "success", "completed": True},
                "outputs": {"9": {"images": [{"filename": "o.png", "subfolder": "", "type": "output"}]}},
            }
        }
    )
    httpserver.expect_request("/view", query_string={"filename": "o.png", "subfolder": "", "type": "output"}).respond_with_data(_jpeg())

    result = plugin.mp_filter_pipeline_step(image, "FilterAiRestyler.medieval", preview=False)

    assert result and result.size == INPUT_SIZE
    submitted = httpserver.log[1][0].get_json()["prompt"]
    assert submitted["1"]["inputs"]["image"] == "up.jpg"
    assert "medieval" in submitted["2"]["inputs"]["text"]
    assert isinstance(submitted["3"]["inputs"]["seed"], int)
    assert len(input_jpegs) == 1
    assert httpserver.log[0][0].files["image"].read() == input_jpegs[0]


def test_fill_placeholders():
    assert fill_placeholders({"a": ["x {{prompt}} y", "{{seed}}"]}, {"prompt": "p", "seed": 5}) == {"a": ["x p y", 5]}
