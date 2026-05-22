from datetime import datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import DateTime, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from packages.data_access.base import Base

if TYPE_CHECKING:
    from packages.data_access.models.analysis_orm import AnalysisOrm
    from packages.data_access.models.audit_log_orm import AuditLogOrm
    from packages.data_access.models.work_item_orm import WorkItemOrm


class IncidentOrm(Base):
    __tablename__ = "incidents"
    __table_args__ = (Index("ix_incidents_fingerprint", "fingerprint", unique=True),)

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    correlation_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True))
    source: Mapped[str] = mapped_column(String(255))
    exception_type: Mapped[str] = mapped_column(String(500))
    exception_message: Mapped[str] = mapped_column(Text)
    stack_trace: Mapped[str | None] = mapped_column(Text)
    fingerprint: Mapped[str] = mapped_column(String(64))
    priority: Mapped[str] = mapped_column(String(20), default="medium")
    status: Mapped[str] = mapped_column(String(30), default="new")
    raw_payload: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    analyses: Mapped[list["AnalysisOrm"]] = relationship(
        "AnalysisOrm", back_populates="incident", cascade="all, delete-orphan"
    )
    work_items: Mapped[list["WorkItemOrm"]] = relationship(
        "WorkItemOrm", back_populates="incident", cascade="all, delete-orphan"
    )
    audit_logs: Mapped[list["AuditLogOrm"]] = relationship(
        "AuditLogOrm", back_populates="incident"
    )
