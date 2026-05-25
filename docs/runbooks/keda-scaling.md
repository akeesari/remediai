# KEDA Scaling Runbook

## Scope

This runbook covers KEDA scaling behavior for RemediAI workers.

- Agent worker scales on PostgreSQL queue depth:
  `SELECT COUNT(*) FROM incidents WHERE status = 'new'`
- Ingestion worker runs on a cron schedule through KEDA `ScaledJob`.

## Validate Scaling Objects

```bash
kubectl get scaledobject -n <namespace>
kubectl get scaledjob -n <namespace>
```

Describe runtime status:

```bash
kubectl describe scaledobject <release>-remediai-worker-agents -n <namespace>
kubectl describe scaledjob <release>-remediai-worker-ingestion -n <namespace>
```

## Verify Agent Worker Scale-Out

1. Create or ingest incidents with `status='new'`.
2. Watch replicas:

```bash
kubectl get deploy <release>-remediai-worker-agents -n <namespace> -w
```

3. Confirm scale ratio follows configured threshold (`targetQueryValue`).

## Verify Scale-In

1. Drain new incidents by processing them to non-`new` status.
2. Wait for `cooldownPeriod`.
3. Confirm replicas return to `minReplicas`.

## Pause Autoscaling Temporarily

Use Helm overrides to pin worker replicas:

```bash
helm upgrade <release> infrastructure/helm/remediai \
  -n <namespace> \
  --set keda.agentWorker.minReplicas=2 \
  --set keda.agentWorker.maxReplicas=2
```

## Tune Sensitivity

- `keda.agentWorker.targetQueryValue`: incidents per replica.
- `keda.agentWorker.activationTargetQueryValue`: activation floor.
- `keda.agentWorker.pollingInterval`: trigger poll interval (seconds).
- `keda.agentWorker.cooldownPeriod`: scale-in wait (seconds).

## Common Failure Modes

- Database auth failures: check Key Vault secret mapping and `POSTGRES_*` env values.
- Scaler stuck inactive: verify query returns rows for `status='new'`.
- No scaled objects: verify `keda.enabled=true` and component-specific flags are enabled.
