import uuid
from datetime import datetime
from pathlib import Path

from sqlalchemy import UUID, Boolean, DateTime, Enum, ForeignKey, Integer, String
from sqlalchemy.dialects.sqlite import JSON
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.sql import func

from .types import DimensionTypes, MediaitemTypes, PathType


class Base(DeclarativeBase):
    pass


class UsageStats(Base):
    __tablename__ = "usagestats"

    action: Mapped[str] = mapped_column(String, default=None, primary_key=True)
    count: Mapped[int] = mapped_column(Integer, default=0)
    last_used_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ShareLimits(Base):
    __tablename__ = "sharelimits"

    action: Mapped[str] = mapped_column(String, default=None, primary_key=True)
    count: Mapped[int] = mapped_column(Integer, default=0)
    last_used_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Mediaitem(Base):
    __tablename__ = "mediaitems"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), default=uuid.uuid4, primary_key=True)
    media_type: Mapped[MediaitemTypes] = mapped_column(Enum(MediaitemTypes))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    # FIXME: currently the resolution seems only seconds. that means several captures in 1 second cannot be sorted properly later using order_by.
    # Also get_last_item fails to get the last one, because there could be multiple items in 1 seconds. Since this is actually currently a minor
    # issue and mostly relevant for benchmark testing, we might solve in the future only. In tests the last item is queried differently when needed.

    job_identifier: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), default=None)

    unprocessed: Mapped[Path] = mapped_column(PathType)  # the original!
    processed: Mapped[Path] = mapped_column(PathType)  # processed original (aka "full" having the pipeline applied)
    pipeline_config: Mapped[dict] = mapped_column(JSON)  # json config of pipeline? or in separate table?

    show_in_gallery: Mapped[bool] = mapped_column(Boolean, default=True)

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}> id={self.id}, media_type={self.media_type}, unprocessed={self.unprocessed}"


class Cacheditem(Base):
    __tablename__ = "cacheditems"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)

    # following are the unique combination to identify if a cached obj is avail or no
    v3mediaitem_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("mediaitems.id"), index=True)
    dimension: Mapped[DimensionTypes] = mapped_column(Enum(DimensionTypes), index=True)
    processed: Mapped[bool] = mapped_column(Boolean, index=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    filepath: Mapped[Path] = mapped_column(PathType)

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}> id={self.id}, mediaitem_id={self.v3mediaitem_id}, filepath={self.filepath}"
