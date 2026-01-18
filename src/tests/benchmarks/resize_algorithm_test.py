import logging

import cv2
import pytest
from PIL import Image
from PIL.Image import Resampling

logger = logging.getLogger(__name__)


def pil_resize(img: Image.Image, mode: Resampling):
    # Warm‑up to avoid first‑call overhead
    img.resize((int(img.width / 2), int(img.height / 2)), resample=mode)


def cv2_resize(img_np, mode):
    scale_percent = 50  # percent of original size
    width = int(img_np.shape[1] * scale_percent / 100)
    height = int(img_np.shape[0] * scale_percent / 100)
    dim = (width, height)

    # resize image
    cv2.resize(img_np, dim, interpolation=mode)  # bicubic


@pytest.mark.parametrize("name,mode", Resampling.__members__.items())
@pytest.mark.benchmark(group="resize_algo")
def test_pil_resize(name, mode, benchmark):
    img = Image.open("src/tests/assets/input.jpg")
    img.load()
    benchmark(pil_resize, img=img, mode=mode)


@pytest.mark.parametrize(
    "name,mode",
    [
        ["INTER_NEAREST", cv2.INTER_NEAREST],
        ["INTER_LINEAR", cv2.INTER_LINEAR],
        ["INTER_CUBIC", cv2.INTER_CUBIC],
        ["INTER_AREA", cv2.INTER_AREA],
        ["INTER_LANCZOS4", cv2.INTER_LANCZOS4],
        ["INTER_LINEAR_EXACT", cv2.INTER_LINEAR_EXACT],
        ["INTER_NEAREST_EXACT", cv2.INTER_NEAREST_EXACT],
    ],
)
@pytest.mark.benchmark(group="resize_algo")
def test_cv2_resize(name, mode, benchmark):
    img = "src/tests/assets/input.jpg"
    img_np = cv2.imread(img, cv2.IMREAD_COLOR)
    assert img_np is not None
    benchmark(cv2_resize, img_np=img_np, mode=mode)
