# Phase 26 — KEDA Autoscaling

## Goal

Configure KEDA (Kubernetes Event-Driven Autoscaling) to scale the Agent Worker
deployment based on Azure Service Bus queue depth, and the Ingestion Worker
based on a time-of-day schedule.  This ensures the platform handles burst
incident volumes without manual intervention.

---

## Background

ARCHITECTURE.md lists KEDA as the autoscaling mechanism for the agent worker.
The Agent Worker currently runs as a fixed single-replica deployment (Phase 24).
Under high incident volume the single pod becomes a bottleneck.

---

## Deliverables

| Artifact | Description |
|---|---|
| `helm/remediai/templates/worker-agents/scaledobject.yaml` | KEDA `ScaledObject` for Agent Worker (Service Bus trigger) |
| `helm/remediai/templates/worker-ingestion/scaledjob.yaml` | KEDA `ScaledJob` for Ingestion Worker (cron trigger) |
| `helm/remediai/templates/triggerauthentication.yaml` | `TriggerAuthentication` using Workload Identity |
| Updated `helm/remediai/values.yaml` | KEDA scaling parameters |
| `docs/runbooks/keda-scaling.md` | Runbook: how to tune thresholds, disable scaling in an incident |

---

## Agent Worker — Service Bus `ScaledObject`

```yaml
apiVersion: keda.sh/v1alpha1
kind: ScaledObject
metadata:
  name: remediai-agent-worker
spec:
  scaleTargetRef:
    name: remediai-worker-agents
  minReplicaCount: 1
  maxReplicaCount: 10
  cooldownPeriod: 60        # seconds before scaling down
  pollingInterval: 15       # seconds between queue depth checks
  triggers:
    - type: azure-servicebus
      authenticationRef:
        name: remediai-trigger-auth
      metadata:
        namespace: remediai-servicebus
        topicName: incident-events
        subscriptionName: agent-worker-sub
        messageCount: "5"   # target: 1 replica per 5 pending messages
        activationMessageCount: "1"
```

**Scaling logic:**
- Scale up: 1 replica added per 5 pending messages in the subscription.
- Scale down: replicas reduced when queue drains; cooldown prevents flapping.
- Minimum 1 replica always running (no scale-to-zero for the agent worker —
  cold start latency would exceed the 3-minute SLA).
- Maximum 10 replicas — set to respect Azure OpenAI rate limits.

---

## Ingestion Worker — Cron `ScaledJob`

The Ingestion Worker is a short-lived job (KQL poll → publish → exit).  KEDA
replaces the Kubernetes `CronJob` (Phase 24) with a `ScaledJob` for more
precise lifecycle control:

```yaml
apiVersion: keda.sh/v1alpha1
kind: ScaledJob
metadata:
  name: remediai-ingestion-worker
spec:
  jobTargetRef:
    template:
      spec:
        containers:
          - name: ingestion-worker
            image: {{ .Values.workerIngestion.image }}:{{ .Values.global.imageTag }}
  triggers:
    - type: cron
      metadata:
        timezone: UTC
        start: "*/5 * * * *"   # every 5 minutes
        end:   "*/5 * * * *"
        desiredReplicas: "1"
  successfulJobsHistoryLimit: 3
  failedJobsHistoryLimit: 5
```

---

## `TriggerAuthentication`

```yaml
apiVersion: keda.sh/v1alpha1
kind: TriggerAuthentication
metadata:
  name: remediai-trigger-auth
spec:
  podIdentity:
    provider: azure-workload
    identityId: {{ .Values.workloadIdentity.clientId }}
```

Workload Identity eliminates the need for a Service Bus connection string in
the KEDA trigger.

---

## `values.yaml` Additions

```yaml
keda:
  agentWorker:
    minReplicas: 1
    maxReplicas: 10
    messageCountPerReplica: 5
    cooldownPeriod: 60
    pollingInterval: 15
    serviceBusNamespace: ""
    topicName: incident-events
    subscriptionName: agent-worker-sub
  ingestionWorker:
    cronSchedule: "*/5 * * * *"
    timezone: UTC
```

---

## Rate Limit Alignment

Azure OpenAI TPM (tokens per minute) limits constrain the effective maximum
replica count.  The `maxReplicaCount: 10` default assumes a GPT-4o deployment
with a 100K TPM limit and ~10K TPM per pipeline run average.  Operators must
adjust `keda.agentWorker.maxReplicas` if the deployment limit is different.

Document this constraint in `docs/runbooks/keda-scaling.md`.

---

## Runbook (`docs/runbooks/keda-scaling.md`)

Covers:
1. How to check current replica count and queue depth.
2. How to temporarily pause autoscaling (set `minReplicas = maxReplicas = N`).
3. How to tune `messageCountPerReplica` without a full deploy.
4. How to diagnose KEDA `ScaledObject` errors (`kubectl describe scaledobject`).

---

## Acceptance Criteria

- `helm lint` passes with KEDA templates included.
- `kubectl apply` of KEDA manifests succeeds on a KEDA-enabled AKS cluster.
- Queue depth of 15 messages → 3 agent worker replicas (verified in staging).
- Queue drained → replicas return to 1 within `cooldownPeriod` seconds.
- Ingestion worker job runs once per 5-minute interval (verified via `kubectl get jobs`).
- `TriggerAuthentication` uses Workload Identity — no connection strings in the manifest.

---

## Out of Scope

- KEDA operator installation on the AKS cluster (assumed installed via Helm add-on).
- Azure OpenAI deployment scaling or model quota management.
- Prometheus-based scaling triggers.
