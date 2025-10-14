from collections.abc import Generator
from pathlib import Path

import pytest
from PIL import Image

from photobooth.utils.rembg.rembg import remove
from photobooth.utils.rembg.session_factory import new_session
from photobooth.utils.rembg.sessions import sessions_names
from photobooth.utils.rembg.sessions.base import BaseSession


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
