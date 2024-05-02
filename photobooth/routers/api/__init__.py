"""Example 2nd-level subpackage."""

from fastapi import APIRouter

from . import actions, aquisition, config, debug, mediacollection, mediaprocessing, print, sse, system

__all__ = [
    "actions",
    "aquisition",  # refers to the 'aquisition.py' file
    "config",  # refers to the 'config.py' file
    "debug",
    "mediacollection",
    "mediaprocessing",
    "print",
    "sse",
    "system",
]

router = APIRouter(prefix="/api")
router.include_router(actions.router)
router.include_router(aquisition.router)
router.include_router(config.router)
router.include_router(debug.router)
router.include_router(mediacollection.router)
router.include_router(mediaprocessing.router)
router.include_router(print.router)
router.include_router(sse.router)
router.include_router(system.router)
