# Key Vault Secret Rotation Runbook

## Scope

This runbook covers rotating secrets consumed by RemediAI workloads through
Azure Key Vault and the Secrets Store CSI Driver.

## Prerequisites

- Access to the target Key Vault.
- Access to the AKS namespace running RemediAI.
- Helm release name and namespace.

## Rotate Azure DevOps PAT

1. Create a new PAT in Azure DevOps with least privilege.
2. Update the Key Vault secret used by `azure-devops-pat`.
3. Verify the SecretProviderClass object name still matches the configured key.
4. Restart the agent worker deployment to force an immediate remount:

```bash
kubectl rollout restart deployment/<release>-remediai-worker-agents -n <namespace>
```

5. Confirm bug creation and repo read operations still succeed.

## Rotate PostgreSQL Password

1. Update the PostgreSQL credential in the database server.
2. Update the Key Vault secret mapped to `postgres-password`.
3. Restart API and worker workloads:

```bash
kubectl rollout restart deployment/<release>-remediai-api -n <namespace>
kubectl rollout restart deployment/<release>-remediai-worker-agents -n <namespace>
```

4. Confirm connections recover and no authentication failures are logged.

## Validate Mounted Secrets

1. Confirm Secrets Store CSI is mounted:

```bash
kubectl get pods -n <namespace>
kubectl exec -it <pod-name> -n <namespace> -- ls /mnt/secrets-store
```

2. Confirm Kubernetes synced secret exists:

```bash
kubectl get secret <release>-remediai-secrets -n <namespace>
```

## Recovery

If a bad secret value is deployed:

1. Restore the prior secret version in Key Vault.
2. Restart affected workloads.
3. Verify successful health checks and agent processing.
