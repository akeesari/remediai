---
sidebar_position: 1
title: Azure Monitor & Application Insights
---

# Azure Monitor & Application Insights

RemediAI ingests exception data from Application Insights via Azure Monitor KQL queries. This page covers the connection setup, required permissions, and KQL query configuration.

---

## How it works

The Log Ingestion Service runs a scheduled KQL query against the Application Insights instance linked to your Azure Monitor Workspace. It retrieves exceptions logged in the `exceptions` table, deduplicates them by fingerprint, and persists new incidents to PostgreSQL with `status='new'`.

---

## Prerequisites

- An Application Insights resource connected to your .NET application.
- An Azure Monitor Workspace (for Log Analytics queries).
- Managed Identity with **Monitoring Reader** role on the Application Insights resource.

---

## Required role assignment

```bash
# Assign Monitoring Reader to the RemediAI Managed Identity
az role assignment create \
  --assignee <managed-identity-principal-id> \
  --role "Monitoring Reader" \
  --scope /subscriptions/<sub-id>/resourceGroups/<rg>/providers/microsoft.insights/components/<appinsights-name>
```

---

## Environment variables

| Variable | Description | Example |
|----------|-------------|---------|
| `AZURE_APP_INSIGHTS_CONNECTION_STRING` | Application Insights connection string | `InstrumentationKey=...;IngestionEndpoint=...` |
| `AZURE_MONITOR_WORKSPACE_ID` | Log Analytics workspace resource ID | `/subscriptions/.../workspaces/my-workspace` |
| `INGESTION_POLL_INTERVAL` | Poll interval in seconds (default: `60`) | `60` |
| `INGESTION_LOOKBACK_MINUTES` | How far back to query on each poll (default: `5`) | `5` |
| `INGESTION_BATCH_SIZE` | Max exceptions per poll cycle (default: `100`) | `100` |

---

## KQL query

The ingestion service runs this KQL query on each poll cycle:

```kql
exceptions
| where timestamp > ago({lookback_minutes}m)
| where type != ""
| project
    timestamp,
    type,
    outerMessage,
    innermostMessage,
    outerType,
    innermostType,
    assembly,
    method,
    outerAssembly,
    details,
    cloud_RoleName,
    operation_Id,
    operation_ParentId,
    client_IP,
    user_Id
| order by timestamp desc
| take {batch_size}
```

Replace `{lookback_minutes}` and `{batch_size}` with the configured values.

---

## Fingerprinting

Each exception is fingerprinted before storage:

```python
def compute_fingerprint(exception_type: str, stack_trace: str) -> str:
    normalized = re.sub(r'\s+at\s+', ' at ', stack_trace)
    normalized = re.sub(r':line \d+', '', normalized)   # strip line numbers
    normalized = re.sub(r'0x[0-9a-fA-F]+', '0xADDR', normalized)  # strip addresses
    return sha256(f"{exception_type}::{normalized}".encode()).hexdigest()
```

Exceptions with a known fingerprint in a non-resolved incident are skipped to prevent duplicates.

---

## Supported .NET telemetry

RemediAI reads from the standard Application Insights `exceptions` table, populated by:

- **Application Insights SDK** (`Microsoft.ApplicationInsights`)
- **OpenTelemetry** with the Azure Monitor exporter (`Azure.Monitor.OpenTelemetry.Exporter`)

Both approaches populate the `exceptions` table with `type`, `outerMessage`, and `details` (stack frames).

---

## Testing the connection

```bash
# From the repo root with your .env loaded
python -c "
from packages.integrations.azure_monitor import AzureMonitorClient
import asyncio

async def test():
    client = AzureMonitorClient()
    results = await client.query_recent_exceptions(lookback_minutes=60, batch_size=5)
    print(f'Found {len(results)} exceptions')
    for r in results:
        print(f'  {r.exception_type}: {r.exception_message[:80]}')

asyncio.run(test())
"
```

---

## Troubleshooting

| Symptom | Check |
|---------|-------|
| No exceptions returned | Verify Managed Identity has Monitoring Reader role |
| `AuthorizationFailed` | Check the `AZURE_MONITOR_WORKSPACE_ID` is the workspace linked to Application Insights |
| `QuerySyntaxError` | Ensure `INGESTION_LOOKBACK_MINUTES` is an integer |
| Exceptions appear as duplicates | Check the fingerprint column in the `incidents` table — same fingerprint should produce one row |
