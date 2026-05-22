from datetime import datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Index, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from packages.data_access.base import Base

if TYPE_CHECKING:
    from packages.data_access.models.incident_orm import IncidentOrm


class AnalysisOrm(Base):
    __tablename__ = "incident_analyses"
    __table_args__ = (Index("ix_incident_analyses_incident_id", "incident_id"),)

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    incident_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("incidents.id", ondelete="CASCADE")
    )
    root_cause: Mapped[str | None] = mapped_column(Text)
    root_cause_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    recommendations: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    code_snippets: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    rag_results: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    agent_trace: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    incident: Mapped["IncidentOrm"] = relationship("IncidentOrm", back_populates="analyses")
