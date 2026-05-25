# Provider Model

## Overview

RemediAI uses a profile-based provider model:

- `azure-foundry` (default): Azure AI Foundry / Azure OpenAI optimized path.
- `portable`: cloud-agnostic adapter path for non-Azure Kubernetes clusters.

The runtime resolves provider IDs from settings and constructs adapters through
`packages.integrations.providers.registry`.

## Scope

Phase 32 introduces provider abstraction for configuration and bootstrap
resolution without changing agent business logic.

Current adapter boundary:

- LLM provider resolution

Planned follow-up adapters:

- Retrieval provider
- SCM provider
- Ticket provider

## Runtime Rules

1. Profile defaults to `azure-foundry`.
2. Provider combinations are validated at startup.
3. Agent runtime modules depend on provider registry interfaces, not cloud SDK
   classes directly.
4. Credentials are sourced from settings and must be backed by secret
   management in production.
