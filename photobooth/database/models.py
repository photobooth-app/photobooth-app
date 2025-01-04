import uuid
from datetime import datetime
from enum import StrEnum
from pathlib import Path

from sqlalchemy.dialects.sqlite import JSON
from sqlalchemy.types import String, TypeDecorator
from sqlmodel import Column, Field, SQLModel


class PathType(TypeDecorator):
    impl = String

    def process_bind_param(self, value, dialect):
        if isinstance(value, Path):
            return str(value)
        return value

    def process_result_value(self, value, dialect):
        if value is not None:
            return Path(value)
        return value


class UsageStats(SQLModel, table=True):
    action: str = Field(default=None, primary_key=True)
    count: int = Field(default=0)
    last_used_at: datetime | None = Field(
        default_factory=datetime.now().astimezone,
    )


class ShareLimits(SQLModel, table=True):
    action: str = Field(default=None, primary_key=True)
    count: int = Field(default=0)
    last_used_at: datetime | None = Field(
        default_factory=datetime.now().astimezone,
    )


class MediaitemTypes(StrEnum):
    image = "image"  # captured single image that is NOT part of a collage (normal process)
    collage = "collage"  # canvas image that was made out of several collage_image
    animation = "animation"  # canvas image that was made out of several animation_image
    video = "video"  # captured video - h264, mp4 is currently well supported in browsers it seems
    multicamera = "multicamera"  #  video - h264, mp4, result of multicamera image, example the wigglegram


class V3MediaitemBase(SQLModel):
    media_type: MediaitemTypes
    created_at: datetime = Field(default_factory=datetime.now)


class V3Mediaitem(V3MediaitemBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)

    job_identifier: uuid.UUID | None = Field(default=None, description="Assign items during capture to the specific job.")

    unprocessed: Path = Field(sa_column=Column(PathType))  # the original!
    processed: Path = Field(sa_column=Column(PathType))  # processed original (aka "full" having the pipeline applied)
    pipeline_config: dict = Field(sa_column=Column(JSON))  # json config of pipeline? or in separate table?

    show_in_gallery: bool = Field(default=True)


class V3MediaitemPublic(V3MediaitemBase):
    id: uuid.UUID


class DimensionTypes(StrEnum):
    full = "full"
    preview = "preview"
    thumbnail = "thumbnail"


class V3CachedItem(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)

    v3mediaitem_id: uuid.UUID = Field(index=True)
    dimension: DimensionTypes = Field(index=True)

    created_at: datetime = Field(default_factory=datetime.now)

    filepath: Path = Field(sa_column=Column(PathType))
