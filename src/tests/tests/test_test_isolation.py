import os
import sqlite3
import subprocess
import sys
from contextlib import closing
from pathlib import Path

import pytest


def _pytest_environment() -> dict[str, str]:
    environment = os.environ.copy()
    environment.pop("PYTEST_ADDOPTS", None)
    environment.pop("PYTEST_CURRENT_TEST", None)
    return environment


@pytest.mark.parametrize(
    ("test_node", "extra_args"),
    [
        ("tests/services/test_collection.py::test_delete_item", ()),
        (
            "benchmarks/filter_pilgram2_test.py::test_pilgram_lores_benchmark[_1977]",
            ("--benchmark-only", "--benchmark-autosave", "--benchmark-min-rounds=1", "--benchmark-min-time=0.005", "--benchmark-max-time=0.01"),
        ),
    ],
)
def test_existing_database_and_media_are_not_touched(tmp_path: Path, test_node: str, extra_args: tuple[str, ...]):
    user_directory = tmp_path / "existing-data"
    database = user_directory / "database/database.sqlite"
    database.parent.mkdir(parents=True)

    with closing(sqlite3.connect(database)) as connection:
        connection.execute("CREATE TABLE sentinel (value TEXT NOT NULL)")
        connection.execute("INSERT INTO sentinel VALUES ('keep')")
        connection.commit()
    original_database = database.read_bytes()

    sentinels = [
        user_directory / "media/unprocessed_original/keep.jpg",
        user_directory / "media/camera_original/keep.jpg",
        user_directory / "media/processed_full/keep.jpg",
        user_directory / "cache/keep.jpg",
        user_directory / "tmp/keep/keep.txt",
    ]
    for sentinel in sentinels:
        sentinel.parent.mkdir(parents=True, exist_ok=True)
        sentinel.write_text("keep")

    runner = """
import os
import sys
import pytest

class ClearCollection:
    @pytest.hookimpl(tryfirst=True)
    def pytest_runtest_call(self):
        from photobooth.database.database import engine
        from photobooth.services.collection import MediacollectionService

        collection = MediacollectionService()
        collection.clear_all()
        engine.dispose()
        current_directory = os.getcwd()
        try:
            os.chdir(sys.argv[1])
            assert collection.count() == 0
        finally:
            os.chdir(current_directory)

raise SystemExit(pytest.main(["-q", "-p", "no:cacheprovider", *sys.argv[2:]], plugins=[ClearCollection()]))
"""
    target = str(Path(__file__).resolve().parents[1] / test_node)
    result = subprocess.run(
        [sys.executable, "-c", runner, str(user_directory), target, *extra_args],
        cwd=user_directory,
        env=_pytest_environment(),
        capture_output=True,
        text=True,
        timeout=120,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert database.read_bytes() == original_database
    for sentinel in sentinels:
        assert sentinel.read_text() == "keep"
    if test_node.startswith("benchmarks/"):
        assert list((user_directory / ".benchmarks").rglob("*.json"))


def test_preimported_application_prevents_test_execution(tmp_path: Path):
    database = tmp_path / "database/database.sqlite"
    database.parent.mkdir()
    database.write_bytes(b"existing database")

    runner = """
import photobooth.database.database
import pytest
import sys

raise SystemExit(pytest.main(["-q", "-p", "no:cacheprovider", sys.argv[1]]))
"""
    target = str(Path(__file__).resolve().parents[1] / "tests/services/test_collection.py::test_delete_item")
    result = subprocess.run(
        [sys.executable, "-c", runner, target],
        cwd=tmp_path,
        env=_pytest_environment(),
        capture_output=True,
        text=True,
        timeout=120,
    )

    assert result.returncode != 0
    assert "fresh process" in result.stderr
    assert database.read_bytes() == b"existing database"


@pytest.mark.parametrize("use_symlink", [False, pytest.param(True, marks=pytest.mark.skipif(sys.platform == "win32", reason="requires symlinks"))])
def test_basetemp_cannot_be_application_data(tmp_path: Path, use_symlink: bool):
    database = tmp_path / "database/database.sqlite"
    database.parent.mkdir()
    database.write_bytes(b"existing database")

    basetemp = database.parent
    if use_symlink:
        basetemp = tmp_path / "test-output"
        basetemp.symlink_to(database.parent, target_is_directory=True)

    target = str(Path(__file__).resolve().parents[1] / "tests/services/test_collection.py::test_delete_item")
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", f"--basetemp={basetemp}", target],
        cwd=tmp_path,
        env=_pytest_environment(),
        capture_output=True,
        text=True,
        timeout=120,
    )

    assert result.returncode != 0
    assert "pytest --basetemp must not point at application data" in result.stderr
    assert database.read_bytes() == b"existing database"


@pytest.mark.skipif(sys.platform == "win32", reason="Windows paths cannot contain '?'")
def test_unsafe_temporary_path_prevents_test_execution(tmp_path: Path):
    database = tmp_path / "existing.sqlite"
    with closing(sqlite3.connect(database)) as connection:
        connection.execute("CREATE TABLE sentinel (value TEXT NOT NULL)")
        connection.execute("INSERT INTO sentinel VALUES ('keep')")
        connection.commit()
    original_database = database.read_bytes()

    temp_directory = tmp_path / "existing.sqlite?temporary"
    temp_directory.mkdir()
    environment = _pytest_environment()
    environment["TMPDIR"] = str(temp_directory)
    target = str(Path(__file__).resolve().parents[1] / "tests/services/test_collection.py::test_delete_item")
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", target],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        timeout=120,
    )

    assert result.returncode != 0
    assert "SQLite interprets it as a URL delimiter" in result.stderr
    assert database.read_bytes() == original_database
