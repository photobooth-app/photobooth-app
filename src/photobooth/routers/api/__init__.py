"""Example 2nd-level subpackage."""

from fastapi import APIRouter

from . import acquisition, actions, config, debug, filter, mediacollection, processing, share, sse, system

__all__ = [
    "actions",
    "acquisition",  # refers to the 'acquisition.py' file
    "config",  # refers to the 'config.py' file
    "debug",
    "mediacollection",
    "processing",
    "filter",
    "share",
    "sse",
    "system",
]

router = APIRouter(prefix="/api")
router.include_router(actions.router)
router.include_router(acquisition.router)
router.include_router(config.router)
router.include_router(debug.router)
router.include_router(mediacollection.router)
router.include_router(processing.router)
router.include_router(filter.router)
router.include_router(share.router)
router.include_router(sse.router)
router.include_router(system.router)
