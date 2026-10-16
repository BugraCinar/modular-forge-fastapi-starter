# Connecting the RAG sibling

[Modular Forge RAG](https://github.com/BugraCinar/modular-forge-rag-starter) runs
document processing and retrieval in a separate service. This backend continues
to own accounts, current-session validation, organization membership and business
permissions. No embedding or model runtime needs to run inside the backend.

## Install and compose

Add the gateway package to your dependency manifest and lockfile. The release
contains a wheel, and the source dependency can target the tagged subdirectory:

```text
modular-forge-rag-fastapi-integration @ git+https://github.com/BugraCinar/modular-forge-rag-starter.git@v1.0.0#subdirectory=integrations/fastapi
```

Wrap the existing application factory in your deployment entry point:

```python
from forge_rag_integration import install
from modular_forge.app import create_app as backend_app


def create_app():
    app = backend_app()
    install(app)
    return app
```

Configure `RAG_MODULE_ENABLED=true`, a fixed `RAG_URL`, and the RAG service's
private `forge-fastapi` delegation key as `RAG_DELEGATION_KEY`. The gateway uses
the existing `current_account` dependency before minting a separate 60-second
delegation. Keep this key separate from `JWT_SECRET`. Use encrypted transport
across machines and keep service credentials out of browser clients.

## Client flow and membership

Clients retain their usual backend bearer token and call `/api/v1/rag/documents`
with an `Idempotency-Key`. A 202 response means queued work; poll
`/api/v1/rag/jobs/{id}` until completed, then query `/api/v1/rag/query`.

The default resolver creates a private per-account tenant. Shared organization
knowledge requires a server-side membership resolver and document ACLs. Never
accept tenant/group authority from client JSON. Apply user/tenant model-spend
quotas alongside the backend's existing request limits.

See the RAG repository's [integration guide](https://github.com/BugraCinar/modular-forge-rag-starter/blob/v1.0.0/integrations/fastapi/README.md)
and [Turkish pipeline walkthrough](https://github.com/BugraCinar/modular-forge-rag-starter/blob/v1.0.0/docs/PIPELINE_TR.md)
for configuration, removal and durable source synchronization. Setting
`RAG_MODULE_ENABLED=false` removes the gateway routes; it does not delete indexed
documents from the separate RAG service.
