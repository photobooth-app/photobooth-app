"""
v4l webcam implementation backend
"""
import logging

from .disabled import DisabledBackend

logger = logging.getLogger(__name__)


class NotavailableBackend(DisabledBackend):
    pass
