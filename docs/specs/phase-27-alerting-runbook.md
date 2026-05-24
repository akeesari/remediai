# Phase 27 — Azure Monitor Alerts + On-Call Runbook

## Goal

Define Azure Monitor alert rules for critical platform failures and publish
operational runbooks so the on-call engineer can diagnose and resolve incidents
without tribal knowledge.

---

## Deliverables

| Artifact | Description |
|---|---|
| `infra/terraform/modules/alerting/main.tf` | Alert rules, action groups, diagnostic settings |
| `docs/runbooks/oncall-overview.md` | On-call quick-reference: services, access, first steps |
| `docs/runbooks/pipeline-failure.md` | Runbook: agent pipeline processing failures |
| `docs/runbooks/ingestion-failure.md` | Runbook: ingestion worker not polling or publishing |
| `docs/runbooks/servicebus-deadletter.md` | Runbook: dead-letter queue growth |
| `docs/runbooks/database-issues.md` | Runbook: PostgreSQL connection failures and slow queries |
| `docs/runbooks/keyvault-rotation.md` | Already defined in Phase 25; verify completeness |
| `docs/runbooks/keda-scaling.md` | Already defined in Phase 26; verify completeness |

---

## Alert Rules

All alerts are defined as `azurerm_monitor_scheduled_query_rules_alert_v2`
or `azurerm_monitor_metric_alert` resources in Terraform.

### Critical Alerts (PagerDuty / on-call escalation)

| Alert Name | Signal | Threshold | Window |
|---|---|---|---|
| `AgentPipelineSLABreach` | App Insights custom metric `pipeline.duration_ms` | p95 > 180,000 ms | 15 min |
| `ServiceBusDeadLetterGrowth` | Service Bus dead letter count | > 10 messages | 5 min |
| `PipelineErrorRate` | App Insights `exceptions/count` for agent worker | > 5% of runs | 10 min |
| `APIHealthCheckFailing` | Availability test (`/health` endpoint) | < 95% success | 5 min |
| `DatabaseConnectionPool` | App Insights custom metric `db.pool.waiting` | > 20 | 5 min |

### Warning Alerts (email / Teams notification only)

| Alert Name | Signal | Threshold | Window |
|---|---|---|---|
| `IngestionWorkerNotRunning` | Log query: no ingestion log events | 0 events | 10 min |
| `AgentWorkerScaleMaxReached` | KEDA replica count = maxReplicas | sustained | 10 min |
| `LLMTokenBudgetWarning` | App Insights metric `openai.tokens_used` | > 80% TPM limit | 5 min |
| `AuditLogGap` | Log query: `audit_log` rows inserted < expected | < 1 row per 5 min when incidents exist | 10 min |

---

## Action Groups

### `remediai-oncall` (Critical)

- Email: on-call distribution list.
- Webhook: PagerDuty Events v2 API integration URL (stored in Key Vault, not hardcoded).
- SMS: configurable via Terraform variable.

### `remediai-warn` (Warning)

- Email: engineering team distribution list.
- Microsoft Teams: webhook to `#remediai-alerts` channel.

---

## Terraform Module (`infra/terraform/modules/alerting/main.tf`)

Resources:
- `azurerm_monitor_action_group` — one for critical, one for warnings.
- `azurerm_monitor_scheduled_query_rules_alert_v2` — for log-based alerts.
- `azurerm_monitor_metric_alert` — for metric-based alerts.
- `azurerm_application_insights_web_test` — for the API availability test.
- `azurerm_monitor_diagnostic_setting` — route AKS, Service Bus, and Key Vault
  diagnostic logs to the Log Analytics workspace.

---

## Runbook Standards

Each runbook must follow this structure:

```markdown
# Runbook: {Alert Name}

## Symptom
What the alert looks like and when it fires.

## Impact
What users or services are affected.

## Triage Steps
1. Step-by-step commands to diagnose (kubectl, az CLI, KQL queries).

## Resolution
Known fixes for common root causes.

## Escalation
Who to page if the runbook doesn't resolve within 30 minutes.
```

---

## `docs/runbooks/oncall-overview.md`

Covers:
- How to access the Azure Portal, AKS cluster, and Log Analytics workspace.
- Key dashboards (Azure Monitor, Application Insights, KEDA metrics).
- Service Bus dead-letter queue inspection commands.
- Contact list: service owners, platform team, Azure support.

---

## Acceptance Criteria

- `terraform validate` and `terraform plan` succeed for the alerting module.
- All 5 critical alert rules are visible in Azure Monitor after `terraform apply`.
- A simulated API health check failure triggers the `APIHealthCheckFailing` alert within 10 minutes.
- Each runbook follows the standard structure and contains working `kubectl` and `az` commands.
- Action group sends a test notification successfully.

---

## Out of Scope

- Grafana dashboard provisioning (separate from Azure Monitor alerts).
- PagerDuty schedule configuration (done outside Terraform by the on-call team).
- SLA reporting dashboards.
