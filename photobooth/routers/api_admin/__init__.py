"""Example 2nd-level subpackage."""

from fastapi import APIRouter

from . import config, files, information

__all__ = [
    "config",  # refers to the 'config.py' file
    "files",
    "information",
]

router = APIRouter(prefix="/api/admin")
router.include_router(config.router)
router.include_router(files.router)
router.include_router(information.router)
