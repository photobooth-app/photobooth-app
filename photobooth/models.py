from datetime import datetime

from sqlmodel import Field, SQLModel


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
