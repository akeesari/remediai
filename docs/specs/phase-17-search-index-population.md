# Phase 17 — AI Search Index Population

## Goal

Define the Azure AI Search index schema and build the tooling to populate it
with runbooks, source code, documentation, and prior fix records.  This is
the prerequisite for the RAG Retrieval Agent to return useful results in
production.

---

## Background

The RAG agent (`packages/agent_runtime/rag/agent.py`) queries Azure AI Search
but the index is currently empty in real deployments.  This phase defines:

1. The index schema (fields, vector dimensions, semantic configuration).
2. A population script for each document source type.
3. A chunking strategy so large documents fit within the search limit.
4. A Makefile target for operators to run the population on-demand.

---

## Deliverables

| Artifact | Description |
|---|---|
| `packages/search/index_schema.py` | Pydantic models for index fields; `create_or_update_index()` function |
| `packages/search/chunker.py` | `chunk_text(text, max_tokens, overlap)` utility |
| `packages/search/indexers/runbook_indexer.py` | Indexes Markdown runbooks from `docs/runbooks/` |
| `packages/search/indexers/source_indexer.py` | Indexes C# source files from a configured repo path or ADO Repos |
| `packages/search/indexers/prior_fix_indexer.py` | Indexes historical fix records from PostgreSQL `incident_analyses` |
| `scripts/populate_search_index.py` | CLI entry point; accepts `--source runbooks|source|prior_fixes|all` |
| `tests/unit/test_chunker.py` | Unit tests for chunk boundaries and overlap |
| `Makefile` update | `index-populate` target |

---

## Index Schema

### Index name: `remediai-incidents`

| Field | Type | Attributes | Notes |
|---|---|---|---|
| `id` | `Edm.String` | key, filterable | SHA-256 of source path + chunk index |
| `source_type` | `Edm.String` | filterable, facetable | `runbook \| prior_fix \| documentation \| source_code` |
| `title` | `Edm.String` | searchable | Document or file title |
| `content` | `Edm.String` | searchable | Chunked text body |
| `content_vector` | `Collection(Edm.Single)` | — | Embedding vector (1536 dims for `text-embedding-3-small`) |
| `url` | `Edm.String` | — | Link back to source (ADO URL or doc path) |
| `repo` | `Edm.String` | filterable | ADO repo name (for source_code type) |
| `file_path` | `Edm.String` | filterable | Relative file path |
| `exception_type` | `Edm.String` | filterable | For `prior_fix` type: the exception that was fixed |
| `created_at` | `Edm.DateTimeOffset` | sortable | Document creation or index date |

**Semantic configuration:** `title` as title field; `content` as content field.
**Vector profile:** HNSW algorithm; cosine similarity metric.

---

## Chunking Strategy

- Target chunk size: **512 tokens** (≈ 2000 characters).
- Overlap between chunks: **50 tokens** to preserve sentence context at boundaries.
- Heading-aware: Markdown `##` headings start a new chunk boundary.
- Minimum chunk size: **100 tokens** — discard smaller trailing chunks.
- Chunk ID: `f"{source_id}::chunk{n}"`.

---

## Indexers

### Runbook Indexer

- Reads all `*.md` files under `docs/runbooks/`.
- Splits by the chunking strategy.
- Sets `source_type = "runbook"`.
- `title` = first `#` heading in the file.

### Source Code Indexer

- Fetches C# (`.cs`) files from Azure DevOps Repos via the existing
  `AzureDevOpsReposClient`.
- Filters to files under configured namespace prefixes (e.g., `src/`).
- Strips comment blocks before chunking to reduce noise.
- Sets `source_type = "source_code"`.

### Prior Fix Indexer

- Queries `incident_analyses` table for rows where `recommendations` is
  non-empty and `status = "resolved"`.
- Builds a document: exception type + root cause summary + top recommendation.
- Sets `source_type = "prior_fix"`, `exception_type` = the original exception.

---

## Embedding Generation

- Model: `text-embedding-3-small` via Azure OpenAI.
- Embeddings generated in batches of 50 chunks to respect rate limits.
- Exponential backoff (3 retries) on 429 responses.
- Embeddings stored in `content_vector` field.

---

## Configuration

New settings in `packages/config/settings.py`:

```python
search_index_name: str = "remediai-incidents"
openai_embedding_model: str = "text-embedding-3-small"
openai_embedding_deployment: str = ""  # Azure OpenAI deployment name
ado_source_repo: str = ""              # Repo to index for source_code type
ado_source_path_prefix: str = "src/"  # Only index files under this path
```

---

## Makefile Target

```makefile
index-populate:
    $(PYTHON) scripts/populate_search_index.py --source all
```

---

## Acceptance Criteria

- `scripts/populate_search_index.py --source runbooks` indexes all files in
  `docs/runbooks/` without error.
- `test_chunker.py` unit tests pass: boundary correctness, overlap, heading split.
- Index schema is created idempotently (safe to re-run).
- `ruff check .` and `mypy apps/ packages/ --strict` pass.

---

## Out of Scope

- Automated incremental indexing (future phase).
- SharePoint or Confluence document connectors.
- Custom embedding model fine-tuning.
