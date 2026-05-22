from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from packages.data_access.base import Base

if TYPE_CHECKING:
    from packages.data_access.models.incident_orm import IncidentOrm


class WorkItemOrm(Base):
    __tablename__ = "work_items"
    __table_args__ = (Index("ix_work_items_incident_id", "incident_id"),)

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    incident_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("incidents.id", ondelete="CASCADE")
    )
    item_type: Mapped[str] = mapped_column(String(20), default="bug")
    ado_item_id: Mapped[int] = mapped_column(Integer)
    ado_item_url: Mapped[str] = mapped_column(String(1000))
    pr_url: Mapped[str | None] = mapped_column(String(1000))
    pr_branch: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    incident: Mapped["IncidentOrm"] = relationship("IncidentOrm", back_populates="work_items")
