from datetime import datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from packages.data_access.base import Base

if TYPE_CHECKING:
    from packages.data_access.models.incident_orm import IncidentOrm


class AuditLogOrm(Base):
    __tablename__ = "audit_log"
    __table_args__ = (
        Index("ix_audit_log_incident_id", "incident_id"),
        Index("ix_audit_log_timestamp", "timestamp"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    incident_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("incidents.id", ondelete="SET NULL")
    )
    agent_name: Mapped[str] = mapped_column(String(100))
    action: Mapped[str] = mapped_column(String(255))
    actor_identity: Mapped[str | None] = mapped_column(String(255))
    log_metadata: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, default=dict)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    incident: Mapped["IncidentOrm | None"] = relationship(
        "IncidentOrm", back_populates="audit_logs"
    )
