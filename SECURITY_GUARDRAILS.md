# RemediAI — Security Guardrails

## Principles

1. **Humans approve all code changes.** No automated merges or direct production writes.
2. **Least privilege everywhere.** Every identity, service account, and API token carries only the permissions it needs.
3. **Secrets never in code.** All credentials flow through Azure Key Vault and Managed Identity.
4. **PII masked before LLM.** Exception payloads are scrubbed before transmission to any AI endpoint.
5. **Full audit trail.** Every agent decision is recorded with timestamp, inputs, outputs, and actor identity.
6. **Defence in depth.** Security controls at the network, identity, data, and application layers — not just one.

---

## Identity and Access

### Managed Identity (Workload Identity on AKS)

All platform services authenticate to Azure services using Managed Identity bound to Kubernetes service accounts via Workload Identity Federation. No client secrets or certificates are stored in the cluster.

| Service              | Identity Role                                      |
| -------------------- | -------------------------------------------------- |
| Log Ingestion        | Monitoring Reader on Application Insights resource |
| Agent Worker         | Cognitive Services OpenAI User                     |
| Agent Worker         | Search Index Data Reader                           |
| Agent Worker         | Azure DevOps (PAT via Key Vault)                   |
| Agent Worker         | Storage Blob Data Contributor (evidence only)      |
| Backend API          | Key Vault Secrets User                             |

### Azure DevOps Service Connection

Azure DevOps access uses a scoped Personal Access Token (PAT) stored in Key Vault. The PAT grants:
- Read/Write on Work Items (Bug creation only).
- Read on Repos (code context).
- Write on Repos only in Phase 2 (PR creation) and only on the configured repository.
- No admin, pipeline, or project-level permissions.

---

## Secret Management

- All secrets stored in Azure Key Vault.
- Secrets mounted into pods using the Secrets Store CSI Driver (no environment variable injection of raw secrets).
- Key Vault access policies scoped per Managed Identity.
- Secret rotation enforced via Key Vault rotation policies for database credentials.
- No secrets in source code, Dockerfiles, Helm values, or pipeline YAML.
- `detect-secrets` pre-commit hook blocks accidental secret commits.

---

## PII and Data Handling

### Scrubbing Before LLM Transmission

Exception payloads may contain PII (email addresses, usernames, IP addresses, file paths with user data). Before any payload is sent to Azure OpenAI:

1. Run a regex-based scrubber against the exception message and stack trace.
2. Replace matched PII with placeholder tokens: `[EMAIL]`, `[IP]`, `[USERNAME]`.
3. Log the scrubbing operation (not the original values) in the audit log.
4. Store the scrubbed payload only.

Scrubbing patterns cover at minimum: email addresses, IPv4/IPv6 addresses, Azure subscription IDs, UUIDs that appear to be user identifiers, credit card patterns, and Azure storage SAS tokens.

### Data Residency

All processing and storage occurs within the configured Azure region. No cross-region replication unless explicitly enabled by the platform operator. Azure OpenAI deployments must be in the same region as the AKS cluster.

### Retention

| Data Type          | Retention Period | Notes                            |
| ------------------ | ---------------- | -------------------------------- |
| Raw exception logs | 90 days          | Purged after incident analysis   |
| Incident records   | 2 years          | Required for audit               |
| Audit log          | 3 years          | Immutable once written           |
| Evidence bundles   | 1 year           | Blob Storage lifecycle policy    |
| LLM prompt/response| Not retained     | Never stored; scrubbed before use|

---

## Network Security

- All inter-service communication within AKS uses Kubernetes Network Policies.
- AKS cluster is private (private API server endpoint).
- Key Vault, Azure AI Search, Blob Storage, and other Azure PaaS dependencies are accessed via Private Endpoints.
- PostgreSQL and Redis run as internal AKS services and are not exposed publicly.
- No public endpoints on internal services.
- Ingress to the React dashboard and FastAPI via Azure Application Gateway with WAF (OWASP 3.2 ruleset).
- TLS 1.2+ enforced on all endpoints. TLS 1.0/1.1 disabled.

---

## Application Security

### Input Validation

- All API inputs validated via Pydantic models with strict field types.
- No raw SQL construction — SQLAlchemy ORM or parameterized queries only.
- KQL queries to Azure Monitor are parameterized; no user-controlled KQL injection vectors.

### Agent Safety

- Agents operate read-only on Azure Monitor and Azure DevOps Repos (except Bug creation and Phase 2 PR creation).
- Agent actions are bounded: the Fix Planner recommends; it does not apply changes.
- PR creation (Phase 2) requires an explicit human approval event stored in the database before the PR Agent runs.
- Agents do not execute arbitrary code from LLM outputs.
- No tools exposed to LLM that can execute shell commands or make unauthenticated HTTP calls.

### Dependency Security

- `pip-audit` and `npm audit` run in CI on every PR.
- Base images pinned by digest, not tag.
- Container images scanned with Microsoft Defender for Containers.
- No `latest` tags in production Helm values.

---

## Audit Trail

Every agent action writes an immutable record to the `audit_log` table:

| Field           | Description                                      |
| --------------- | ------------------------------------------------ |
| `id`            | UUID                                             |
| `incident_id`   | Linked incident                                  |
| `agent_name`    | Which agent ran                                  |
| `action`        | What the agent did                               |
| `input_summary` | Scrubbed summary of agent inputs                 |
| `output_summary`| Summary of agent outputs                         |
| `actor_identity`| Managed Identity or user ID that triggered the run|
| `metadata`      | Additional context (model version, prompt version)|
| `created_at`    | Immutable timestamp                              |

Audit log rows are append-only. No `UPDATE` or `DELETE` is permitted on this table by the application service accounts.

---

## Incident Response

### Runbook Location

Operational runbooks for RemediAI incidents are stored in `docs/runbooks/` and indexed in Azure AI Search.

### Breach or Misuse Indicators

- Unexpected work items created in Azure DevOps not linked to known incidents.
- LLM calls with unusually large token counts (potential prompt injection from malicious exception messages).
- Service Bus dead-letter queue growth (potential processing failures hiding data).
- Audit log gaps (rows missing for expected agent runs).

### On Detection

1. Disable the affected Managed Identity or revoke the ADO PAT immediately.
2. Quarantine the incident record.
3. Review the `audit_log` for the affected `incident_id`.
4. File a security incident in Azure DevOps Boards.
5. Notify the platform owner and security team.

---

## Responsible Disclosure

If you discover a security vulnerability in RemediAI, please do **not** open a public GitHub issue. Follow the process described in [SECURITY.md](SECURITY.md) to report it privately.

---

## Compliance Notes

- This platform does not process payment data and is not in PCI scope.
- PII handling follows GDPR/privacy-by-design principles: collect minimum, scrub before AI, retain with defined TTL.
- All agent decisions are auditable: this satisfies typical enterprise AI governance requirements for explainability of automated actions.
- No autonomous code merges: this addresses AI safety requirements in regulated environments.
