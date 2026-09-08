from __future__ import annotations

import enum
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class TaskStatus(str, enum.Enum):
    pending = "pending"
    queued = "queued"
    running = "running"
    completed = "completed"
    failed = "failed"
    stopped = "stopped"


class TestTask(Base):
    __tablename__ = "test_tasks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(120))
    device: Mapped[str] = mapped_column(String(255), index=True)
    test_type: Mapped[str] = mapped_column(String(40))
    parameters_json: Mapped[str] = mapped_column(Text)
    device_info_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    fio_command_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default=TaskStatus.pending.value, index=True)
    progress: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    ended_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_seconds: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    result_dir: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    result_summary_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    smart_before_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    smart_after_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    pid: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    deleted: Mapped[int] = mapped_column(Integer, default=0)
