"""Example 2nd-level subpackage."""

from fastapi import APIRouter

from . import config, files, utils

__all__ = [
    "config",  # refers to the 'config.py' file
    "files",
]

router = APIRouter(prefix="/api/admin")
router.include_router(config.router)
router.include_router(files.router)
