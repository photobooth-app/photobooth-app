import os
from pathlib import Path

import pytest

from photobooth.utils.helper import filenames_sanitize


def test_filenames_sanitize_accepts_path_inside_base(tmp_path: Path):
    base = tmp_path / "data"

    assert filenames_sanitize("nested/file.png", base) == base / "nested" / "file.png"


def test_filenames_sanitize_rejects_sibling_with_common_prefix(tmp_path: Path):
    base = tmp_path / "data"

    with pytest.raises(ValueError):
        filenames_sanitize("../data-elsewhere/file.png", base)


def test_filenames_sanitize_accepts_files_under_root():
    root = Path(os.path.abspath(os.sep))

    assert filenames_sanitize("tmp/file.png", root) == root / "tmp" / "file.png"
