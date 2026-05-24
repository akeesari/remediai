from packages.data_access.base import Base
from packages.data_access.models import AnalysisOrm, AuditLogOrm, IncidentOrm, WorkItemOrm


def test_incident_orm_table_name() -> None:
    assert IncidentOrm.__tablename__ == "incidents"


def test_analysis_orm_table_name() -> None:
    assert AnalysisOrm.__tablename__ == "incident_analyses"


def test_work_item_orm_table_name() -> None:
    assert WorkItemOrm.__tablename__ == "work_items"


def test_audit_log_orm_table_name() -> None:
    assert AuditLogOrm.__tablename__ == "audit_log"


def test_all_orm_models_inherit_base() -> None:
    for model in (IncidentOrm, AnalysisOrm, WorkItemOrm, AuditLogOrm):
        assert issubclass(model, Base)


def test_incident_orm_required_columns() -> None:
    col_names = {c.name for c in IncidentOrm.__table__.columns}
    required = {
        "id",
        "correlation_id",
        "source",
        "exception_type",
        "exception_message",
        "stack_trace",
        "fingerprint",
        "priority",
        "status",
        "raw_payload",
        "created_at",
        "updated_at",
    }
    assert required.issubset(col_names)


def test_incident_orm_fingerprint_unique_index() -> None:
    index_names = {i.name for i in IncidentOrm.__table__.indexes}
    assert "ix_incidents_fingerprint" in index_names


def test_incident_orm_fingerprint_index_is_unique() -> None:
    for index in IncidentOrm.__table__.indexes:
        if index.name == "ix_incidents_fingerprint":
            assert index.unique
            break


def test_analysis_orm_has_incident_fk() -> None:
    fk_targets = {
        fk.column.table.name for col in AnalysisOrm.__table__.columns for fk in col.foreign_keys
    }
    assert "incidents" in fk_targets


def test_analysis_orm_has_index_on_incident_id() -> None:
    index_names = {i.name for i in AnalysisOrm.__table__.indexes}
    assert "ix_incident_analyses_incident_id" in index_names


def test_work_item_orm_has_incident_fk() -> None:
    fk_targets = {
        fk.column.table.name for col in WorkItemOrm.__table__.columns for fk in col.foreign_keys
    }
    assert "incidents" in fk_targets


def test_work_item_orm_has_index_on_incident_id() -> None:
    index_names = {i.name for i in WorkItemOrm.__table__.indexes}
    assert "ix_work_items_incident_id" in index_names


def test_audit_log_orm_has_nullable_incident_fk() -> None:
    incident_id_col = AnalysisOrm.__table__.c["incident_id"]
    assert not incident_id_col.nullable  # analysis always has an incident
    audit_id_col = AuditLogOrm.__table__.c["incident_id"]
    assert audit_id_col.nullable  # audit log can be orphaned


def test_audit_log_orm_has_timestamp_index() -> None:
    index_names = {i.name for i in AuditLogOrm.__table__.indexes}
    assert "ix_audit_log_timestamp" in index_names


def test_incident_orm_stack_trace_is_nullable() -> None:
    col = IncidentOrm.__table__.c["stack_trace"]
    assert col.nullable


def test_analysis_orm_root_cause_is_nullable() -> None:
    col = AnalysisOrm.__table__.c["root_cause"]
    assert col.nullable


def test_session_factory_is_configured() -> None:
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from packages.data_access.session import async_session_factory

    assert isinstance(async_session_factory, async_sessionmaker)
