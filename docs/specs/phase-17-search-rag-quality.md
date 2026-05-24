# Phase 17 — AI Search Index Population + RAG Quality Hardening

## Goal

Populate the Azure AI Search index with runbooks, source code, and prior fix
records so the RAG Retrieval Agent returns useful results in production, then
improve retrieval relevance through hybrid search, query rewriting, and
result re-ranking.

These two concerns were originally separate phases (Search Index and RAG
Quality) but are merged here because the quality work has no value without a
populated index, and both ship before the PR workflow (Phase 19).

---

## Background

The RAG agent (`packages/agent_runtime/rag/agent.py`) queries Azure AI Search
but the index is empty in real deployments.  The current agent also issues a
simple keyword query and takes the top stack frame verbatim — both produce
generic results when the root cause summary is broad or frames point to
framework internals.

---

## Deliverables

### Search Index Population

| Artifact | Description |
|---|---|
| `packages/search/index_schema.py` | Pydantic models for index fields; `create_or_update_index()` function |
| `packages/search/chunker.py` | `chunk_text(text, max_tokens, overlap)` utility |
| `packages/search/indexers/runbook_indexer.py` | Indexes Markdown runbooks from `docs/runbooks/` |
| `packages/search/indexers/source_indexer.py` | Indexes C# source files from ADO Repos |
| `packages/search/indexers/prior_fix_indexer.py` | Indexes historical fix records from `incident_analyses` |
| `scripts/populate_search_index.py` | CLI entry point: `--source runbooks\|source\|prior_fixes\|all` |
| `tests/unit/test_chunker.py` | Unit tests for chunk boundaries and overlap |
| `Makefile` update | `index-populate` target |

### RAG Quality Hardening

| Artifact | Description |
|---|---|
| `packages/agent_runtime/rag/query_builder.py` | `build_search_query(state)` — structured hybrid query from state fields |
| `packages/agent_runtime/rag/reranker.py` | `rerank(results, state)` — post-retrieval re-ranking by source type + exception affinity |
| Updated `packages/agent_runtime/rag/agent.py` | Use `build_search_query` and `reranker`; enable hybrid search |
| Updated `packages/agent_runtime/code_context/frame_filter.py` | Application-frame selection with namespace allow/deny lists |
| `docs/prompts/triage_v2.md` | Refined triage prompt: explicit `service_name` and `affected_service` |
| `docs/prompts/root_cause_v2.md` | Refined root cause prompt: fully qualified `component` path, `affected_namespace` |
| Updated `packages/agent_runtime/prompt_registry.py` | Agents updated to load `v2`; `v1` retained for rollback |
| Updated `tests/agent-evals/test_agent_evals.py` | New eval assertions for RAG result count and recommendation quality |
| Updated agent eval fixtures | Add `rag_results_min_count`, `recommendation_confidence_min` |

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

Reads all `*.md` files under `docs/runbooks/`, splits by chunking strategy,
sets `source_type = "runbook"`, `title` = first `#` heading in the file.

### Source Code Indexer

Fetches C# (`.cs`) files from Azure DevOps Repos via `AzureDevOpsReposClient`,
strips comment blocks before chunking, sets `source_type = "source_code"`.

### Prior Fix Indexer

Queries `incident_analyses` rows where `recommendations` is non-empty and
`status = "resolved"`.  Builds a document: exception type + root cause summary
+ top recommendation.  Sets `source_type = "prior_fix"`.

---

## Embedding Generation

- Model: `text-embedding-3-small` via Azure OpenAI.
- Batches of 50 chunks; exponential backoff (3 retries) on 429 responses.

---

## RAG Query Builder

`build_search_query(state: IncidentState) -> SearchQuery`:

```python
@dataclass
class SearchQuery:
    text: str               # Keyword query string
    vector_text: str        # Text to embed for vector search
    filter_expr: str | None # OData filter (e.g., source_type eq 'runbook')
    top: int                # Max results to return
```

Construction logic:
1. **Text query**: `f"{exception_type} {root_cause_json.component} {root_cause_json.likely_cause}"`.
2. **Vector query**: the full `root_cause_summary` (richer semantic signal).
3. **Filter**: prefer `exception_type` matches in `prior_fix` documents first.
4. **Hybrid mode**: keyword and vector sub-queries submitted in one request.

---

## Result Re-ranker

`rerank(results: list[RAGResult], state: IncidentState) -> list[RAGResult]`:

| Factor | Weight | Description |
|---|---|---|
| Azure AI Search score | 0.5 | Raw relevance from hybrid search |
| Source type priority | 0.3 | `prior_fix=1.0 > runbook=0.75 > documentation=0.5 > source_code=0.25` |
| Exception type affinity | 0.2 | +1.0 if document `exception_type` matches current; else 0 |

Return top 5 re-ranked results with `relevance_score` set to the weighted sum.

---

## Code Context Frame Filter

Replace "top frame only" with:

1. **Deny list**: skip `Microsoft.AspNetCore.*`, `System.*`, `lambda_method*`.
2. **Allow list priority**: frames under `ado_source_path_prefix` ranked first.
3. **Limit**: top 5 application frames after filtering.
4. **Fallback**: if all frames are denied, take top 3 regardless.

---

## Prompt Versioning

### `docs/prompts/root_cause_v2.md`

- `component` must be a fully qualified method path (e.g., `OrderService.CompleteCheckout`).
- Add `affected_namespace` field.
- Distinguish between throw site and root cause.

### `docs/prompts/triage_v2.md`

- Extract `service_name` from stack trace file paths.
- Add `affected_service` to output.

Agents load `v2` by default after this phase; `v1` remains in the registry.

---

## New Settings (`packages/config/settings.py`)

```python
search_index_name: str = "remediai-incidents"
openai_embedding_model: str = "text-embedding-3-small"
openai_embedding_deployment: str = ""  # Azure OpenAI deployment name
ado_source_repo: str = ""              # Repo to index for source_code type
ado_source_path_prefix: str = "src/"  # Only index files under this path
```

---

## Makefile Additions

```makefile
index-populate:
    $(PYTHON) scripts/populate_search_index.py --source all
```

---

## Eval Harness Extensions

Add to each fixture's `expected` block:

```json
{
  "rag_results_min_count": 1,
  "recommendation_confidence_min": 0.6,
  "root_cause_component_not_empty": true
}
```

---

## Acceptance Criteria

- `ruff check .` and `mypy apps/ packages/ --strict` pass.
- All existing tests pass (v1 prompts still work; agents now load v2).
- `scripts/populate_search_index.py --source runbooks` indexes all runbooks.
- `test_chunker.py`: boundary correctness, overlap, heading split.
- Index schema creates idempotently (safe to re-run).
- Re-ranker: given mixed source types, `prior_fix` results appear first.
- Frame filter: framework frames excluded; application frames retained.
- New eval assertions pass against updated fixtures with mocked search results.

---

## Out of Scope

- Automated incremental indexing.
- SharePoint or Confluence document connectors.
- Fine-tuning the embedding model.
- Automated A/B testing of prompt versions in production.
