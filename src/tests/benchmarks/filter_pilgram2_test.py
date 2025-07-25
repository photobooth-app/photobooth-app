import logging

import pilgram2
import pytest
from PIL import Image

logger = logging.getLogger(name=None)


@pytest.fixture(params=pilgram2.__all__)
def filter_algo(request):
    yield request.param


def test_pilgram_lores_benchmark(benchmark, filter_algo):
    with Image.open("src/tests/assets/input_lores.jpg") as im:
        benchmark(getattr(pilgram2, filter_algo), im)


# def test_pilgram_hires_benchmark(benchmark, filter_algo):
#     with Image.open("src/tests/assets/input.jpg") as im:
#         benchmark(getattr(pilgram2, filter_algo), im)


# def test_pilgram_memconsumption():
#     with Image.open("src/tests/assets/input.jpg") as im:
#         # Start tracing memory
#         tracemalloc.start()

#         # Benchmark the function
#         for fun in pilgram2.__all__:
#             getattr(pilgram2, fun)(im)

#         # Get memory snapshot
#         _, peak = tracemalloc.get_traced_memory()
#         tracemalloc.stop()

#         peak_mib = peak / (1024 * 1024)
#         logger.info(f"Peak memory usage = {peak_mib:.2f} MiB")

#         assert peak_mib < 300  # Set reasonable memory threshold
