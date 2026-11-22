import os
import shutil
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest


def _create_test_workspace():
    if "photobooth" in sys.modules:
        raise pytest.UsageError("Tests must run in a fresh process before photobooth is imported, to protect application data.")

    original_directory = Path.cwd()
    workspace = TemporaryDirectory(prefix="photobooth-tests-")
    workspace_path = Path(workspace.name)
    initialized = False

    try:
        if "?" in str(workspace_path):
            raise pytest.UsageError("The temporary directory cannot contain '?' because SQLite interprets it as a URL delimiter.")

        (workspace_path / "src/tests").mkdir(parents=True)
        shutil.copytree(Path(__file__).parent / "assets", workspace_path / "src/tests/assets")
        shutil.copy2(Path(__file__).resolve().parents[2] / ".gitignore", workspace_path / ".gitignore")

        os.chdir(workspace_path)
        import photobooth

        photobooth.DATABASE_PATH = str(workspace_path / "database")
        initialized = True
        return workspace, original_directory
    finally:
        if not initialized:
            os.chdir(original_directory)
            workspace.cleanup()


_workspace: TemporaryDirectory | None = None
_original_directory = Path.cwd()


@pytest.hookimpl(trylast=True)
def pytest_configure(config: pytest.Config):
    global _workspace, _original_directory

    basetemp = config.getoption("basetemp", default=None)
    if basetemp is not None:
        temp_path = (Path.cwd() / basetemp).resolve()
        for name in ("database", "media", "cache", "config", "userdata", "tmp", "recycle", "log", "plugins"):
            data_path = (Path.cwd() / name).resolve()
            if temp_path == data_path or temp_path in data_path.parents or data_path in temp_path.parents:
                raise pytest.UsageError("pytest --basetemp must not point at application data.")

    _workspace, _original_directory = _create_test_workspace()


@pytest.hookimpl(hookwrapper=True, trylast=True)
def pytest_runtestloop():
    try:
        yield
    finally:
        try:
            # Stop background services before restoring the directory for pytest reports.
            if "photobooth.container" in sys.modules:
                from photobooth.container import container

                if container.is_started():
                    container.stop()

            if "photobooth.database.database" in sys.modules:
                from photobooth.database.database import engine

                engine.dispose()
        finally:
            os.chdir(_original_directory)


def pytest_unconfigure():
    if _workspace is not None:
        _workspace.cleanup()
