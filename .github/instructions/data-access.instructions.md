---
applyTo: "packages/data_access/**/*.py,alembic/**/*.py"
---

# Data Access And Migration Rules

- Use SQLAlchemy 2.0 typed ORM patterns (Mapped and mapped_column).
- Keep ORM models aligned with packages/domain models and SPEC.md data model.
- Use Alembic for schema changes; no ad hoc SQL in application code.
- Keep migrations forward-safe and reversible where practical.
- Store timestamps as timezone-aware UTC values.
- Use explicit indexes and constraints for query-critical paths.

## Change Checklist

- ORM model updated
- Migration created or updated
- Unit/integration coverage updated
- ROADMAP.md milestone status updated when a phase item is completed
- Architecture or data model docs updated when schema changes
