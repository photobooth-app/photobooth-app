import logging
from pathlib import Path
from tempfile import NamedTemporaryFile

import pytest

from photobooth.plugins.synchronizer_legacy.utils import get_remote_filepath

logger = logging.getLogger(name=None)


def test_utils_get_remote_filepath(tmp_path: Path):
    with pytest.raises(ValueError):
        assert get_remote_filepath(Path("nonexistant_file_using_default_root_dir.jpg")) is False

    with NamedTemporaryFile(mode="wb", delete=False, dir=tmp_path, prefix="remote_test_") as f:
        assert get_remote_filepath(Path(f.name), local_root_dir=tmp_path)
