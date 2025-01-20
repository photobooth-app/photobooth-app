import logging

import pilgram2  # noqa: F401
import pytest
from PIL import Image

logger = logging.getLogger(name=None)


# 3 filter, dogpatch=fast, clarendon=medium, maven=slow
@pytest.fixture(params=["pilgram2.dogpatch", "pilgram2.clarendon", "pilgram2.maven"])
def library(request):
    yield request.param


@pytest.fixture(params=["tests/assets/input_lores.jpg", "tests/assets/input.jpg"])
def image(request):
    yield request.param


@pytest.mark.benchmark(group="pilgram2")
def test_pilgram2(library, image, benchmark):
    benchmark(eval(library), Image.open(image))
