import logging
from collections.abc import Generator

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


@pytest.mark.benchmark(group="rembg_mask_only")
def test_models_remove_mask(benchmark, _session: BaseSession):
    input_image = Image.open("src/tests/assets/input_lores.jpg")
    input_image.load()

    benchmark(remove, img=input_image, session=_session, mask_only=True)


@pytest.mark.benchmark(group="rembg_cutout")
def test_models_remove_cutout(benchmark, _session: BaseSession):
    input_image = Image.open("src/tests/assets/input_lores.jpg")
    input_image.load()

    benchmark(remove, img=input_image, session=_session)
