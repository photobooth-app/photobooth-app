import logging
import tracemalloc

import pilgram2
import pytest
from PIL import Image

logger = logging.getLogger(name=None)


@pytest.fixture(params=pilgram2.__all__)
def filter_algo(request):
    yield request.param


def test_pilgram_lores_benchmark(benchmark, filter_algo):
    with Image.open("src/tests/assets/input_lores.jpg") as im:
        if filter_algo == "__version__":
            pytest.skip()
        benchmark(getattr(pilgram2, filter_algo), im)


def test_pilgram_hires_benchmark(benchmark, filter_algo):
    with Image.open("src/tests/assets/input.jpg") as im:
        if filter_algo == "__version__":
            pytest.skip()
        benchmark(getattr(pilgram2, filter_algo), im)


def test_pilgram_memconsumption(filter_algo):
    with Image.open("src/tests/assets/input.jpg") as im:
        if filter_algo == "__version__":
            pytest.skip()

        # Start tracing memory
        tracemalloc.start()

        # Benchmark the function
        getattr(pilgram2, filter_algo)(im)

        # Get memory snapshot
        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        peak_mib = peak / (1024 * 1024)
        logger.info(f"{filter_algo}: Peak memory usage = {peak_mib:.2f} MiB")

        assert peak_mib < 300  # Set reasonable memory threshold
