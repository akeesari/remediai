# Phase 4 — Azure Monitor KQL Connector

## Objective

Implement the Azure Monitor / Application Insights connector that polls for new .NET
exceptions using KQL, parses results into domain `Incident` models, scrubs PII, and
persists deduplicated incidents to PostgreSQL. This is the first live data source and
unblocks the ingestion service and all downstream agents.

---

## Files to Create

| Path | Purpose |
|------|---------|
| `packages/integrations/azure_monitor/__init__.py` | Re-exports `AzureMonitorClient` |
| `packages/integrations/azure_monitor/client.py` | `AzureMonitorClient` — async KQL query execution |
| `packages/integrations/azure_monitor/kql_queries.py` | Parameterised KQL query templates |
| `packages/integrations/azure_monitor/parser.py` | Parse `LogsTable` rows → `Incident` domain models |
| `packages/integrations/pii_scrubber.py` | Regex-based PII masking (email, IP, UUID, SAS token) |
| `apps/worker/ingestion/connector.py` | `IngestionConnector` — orchestrates fetch → deduplicate → persist |
| `tests/unit/test_azure_monitor_parser.py` | Parser unit tests (no Azure credentials needed) |
| `tests/unit/test_pii_scrubber.py` | PII scrubber unit tests |
| `tests/integration/test_azure_monitor_connector.py` | Connector integration tests with mock client |

## Files to Modify

| Path | Change |
|------|--------|
| `apps/api/core/config.py` | Add `azure_monitor_app_insights_resource_id` setting |
| `packages/integrations/__init__.py` | Re-export `AzureMonitorClient` |
| `ROADMAP.md` | Check off Azure Monitor KQL connector milestone item |

---

## Dependencies

All already declared in `pyproject.toml`:
- `azure-monitor-query = "^1.3"` — `AsyncLogsQueryClient`
- `azure-identity = "^1.17"` — `DefaultAzureCredential`
- `structlog = "^24.2"` — structured logging
- `sqlalchemy = "^2.0"` — async session for deduplication check

---

## Implementation Notes

### KQL Query Strategy

Queries the Log Analytics workspace backing the Application Insights resource using
`AsyncLogsQueryClient.query_workspace()`. The `exceptions` table is standard in all
workspace-based Application Insights resources.

The parameterised query uses `ago(Nm)` for the lookback window, configurable via
`ingestion_lookback_minutes` (default 10). A 500-row limit prevents runaway ingestion
on first run or after downtime.

### Field Mapping: KQL Row → Incident

| KQL Column | Incident Field | Notes |
|------------|---------------|-------|
| `type` | `exception_type` | Falls back to `innermostType` if blank |
| `outerMessage` | `exception_message` | Falls back to `innermostMessage` |
| `cloud_RoleName` | `source` | Service/app name |
| `details` | `stack_trace` | Dynamic JSON array → joined string |
| `operation_Id` | `correlation_id` | Parsed as UUID; generates new if invalid |
| entire row | `raw_payload` | Full row as dict (PII scrubbed) |

### Fingerprinting and Deduplication

Fingerprint is computed by the `Incident` domain model `model_validator`:
`SHA-256(exception_type + ":" + exception_message[:200])`.

Deduplication in `IngestionConnector` performs a single `SELECT` by fingerprint before
inserting. The unique index on `incidents.fingerprint` provides a database-level
safety net against concurrent inserts.

### PII Scrubbing

Applied at parse time before any field is stored. The scrubber (`pii_scrubber.py`)
replaces:

| Pattern | Replacement |
|---------|------------|
| Email addresses | `[EMAIL]` |
| IPv4 addresses | `[IP]` |
| IPv6 addresses | `[IP]` |
| Azure subscription IDs (GUID in subscription/… path) | `[SUBSCRIPTION_ID]` |
| Azure storage SAS tokens (`sig=…`) | `[SAS_TOKEN]` |
| Freestanding UUIDs (potential user IDs) | `[UUID]` |

The `raw_payload` stored in the DB is also scrubbed. Original values are never
persisted (per `SECURITY_GUARDRAILS.md`).

### Authentication

`AzureMonitorClient` accepts an optional `TokenCredential`. Defaults to
`DefaultAzureCredential`, which resolves to:
- Managed Identity on AKS (production)
- Azure CLI / environment credentials in development

### Error Handling

- `HttpResponseError` from the Azure SDK is logged with `structlog` and re-raised so
  the calling ingestion scheduler can apply retry logic.
- `LogsQueryStatus.PARTIAL` results are accepted with a warning log; partial data is
  better than no data.
- Rows missing mandatory fields (`type`, `outerMessage`) are skipped with a warning.

---

## Acceptance Criteria

- [ ] `pytest tests/unit/test_azure_monitor_parser.py -v` — all tests pass
- [ ] `pytest tests/unit/test_pii_scrubber.py -v` — all tests pass
- [ ] `pytest tests/integration/test_azure_monitor_connector.py -v` — all tests pass
- [ ] `ruff check packages/integrations/ apps/worker/ingestion/` — no errors
- [ ] `mypy packages/integrations/ apps/worker/ingestion/ --strict` — 0 errors
- [ ] Email, IP, UUID, SAS token patterns are all masked in scrubber tests
- [ ] Parser handles missing optional KQL columns without raising

---

## Commit Message

```
feat(integrations): add Azure Monitor KQL connector, PII scrubber, and ingestion connector
```
