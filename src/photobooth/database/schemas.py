import uuid
from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from .types import MediaitemTypes


class UsageStatsPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    action: str
    count: int
    last_used_at: datetime


class ShareLimitsPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    action: str
    count: int
    last_used_at: datetime


class MediaitemPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)  # from_attributes == former from_orm mode

    id: uuid.UUID
    media_type: MediaitemTypes
    created_at: datetime
    updated_at: datetime

    unprocessed: Path
    processed: Path

    show_in_gallery: bool
