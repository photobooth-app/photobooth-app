import logging
import tracemalloc
from collections.abc import Generator
from pathlib import Path

import pytest
from PIL import Image

from photobooth.utils.rembg.rembg import remove
from photobooth.utils.rembg.session_factory import new_session
from photobooth.utils.rembg.sessions import sessions_names
from photobooth.utils.rembg.sessions.base import BaseSession

logger = logging.getLogger(name=None)


@pytest.fixture(params=sessions_names)
def _session(request) -> Generator[BaseSession, None, None]:
    sess = new_session(request.param)
    yield sess


def test_all_models(_session: BaseSession, tmp_path: Path):
    input_image = Image.open("src/tests/assets/input_lores.jpg")

    output_path = tmp_path / "rembg_cutout.png"
    output = remove(input_image, session=_session)
    output.save(output_path)

    output_path = tmp_path / "rembg_mask.png"
    output = remove(input_image, session=_session, only_mask=True)
    output.save(output_path)


def test_pilgram_memconsumption(_session: BaseSession):
    input_image = Image.open("src/tests/assets/input.jpg")

    # Start tracing memory
    tracemalloc.start()

    remove(input_image, session=_session)

    # Get memory snapshot
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    peak_mib = peak / (1024 * 1024)
    logger.info(f"Peak memory usage = {peak_mib:.2f} MiB")

    assert peak_mib < 100  # Set reasonable memory threshold
