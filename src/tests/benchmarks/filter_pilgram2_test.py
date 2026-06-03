import logging

import pilgram2
import pytest
from PIL import Image

logger = logging.getLogger(name=None)


@pytest.fixture(params=pilgram2.__all__)
def filter_algo(request):
    yield request.param


@pytest.mark.benchmark(group="pilgram2")
def test_pilgram_lores_benchmark(benchmark, filter_algo):
    with Image.open("src/tests/assets/input_lores.jpg") as im:
        benchmark(getattr(pilgram2, filter_algo), im)
