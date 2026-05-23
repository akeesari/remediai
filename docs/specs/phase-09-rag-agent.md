# Phase 09 — RAG Retrieval Agent

## Goal

Add a **RAG Retrieval Agent** as the fourth node in the LangGraph pipeline. It queries Azure AI Search using the root cause summary and triage labels, and stores up to five scored `RAGResult` records in `IncidentState`. No LLM call required.

---

## New Files

| Path | Purpose |
|---|---|
| `packages/integrations/azure_search/__init__.py` | Package marker |
| `packages/integrations/azure_search/client.py` | Async wrapper around `azure-search-documents` `AsyncSearchClient` |
| `packages/agent_runtime/rag/__init__.py` | Package marker |
| `packages/agent_runtime/rag/models.py` | `RAGResult` Pydantic model |
| `packages/agent_runtime/rag/agent.py` | `make_rag_node(search_client)` factory + `SearchClientProtocol` |
| `tests/unit/test_rag_agent.py` | Agent node unit tests (mocked search client) |

## Modified Files

| Path | Change |
|---|---|
| `apps/api/core/config.py` | Add `azure_search_api_key` |
| `packages/agent_runtime/pipeline.py` | Add `rag` node; expose `search_client` parameter |
| `tests/integration/test_agent_pipeline.py` | Inject mock search client; assert `rag_results` in state |
| `ROADMAP.md` | RAG Retrieval Agent marked complete |

---

## Agent Contract

**Input fields read:** `root_cause_summary`, `root_cause_json`, `triage_labels`, `exception_type`

**Output fields set:** `rag_results` — list of `RAGResult` dicts

**No LLM call.** The node is I/O-only: build query → search → map → filter → sort.

---

## Query Building

```text
query = "{root_cause_summary} {exception_type} {' '.join(triage_labels)}"
```

Truncated to 1 000 characters before passing to the search API.

---

## Result Filtering and Sorting

1. Filter out results with `relevance_score ≤ 0.6` (Azure Search `@search.score`).
2. Sort by source priority: `runbook > prior_fix > documentation > source_code > (other)`.
3. Return the top 5 after filtering and sorting.

---

## RAGResult Schema

```python
class RAGResult(BaseModel):
    source: str          # e.g. "runbook", "prior_fix", "documentation"
    title: str
    excerpt: str         # first 500 chars of the matched content
    relevance_score: float
    url: str | None
```

---

## Azure AI Search Auth

Prefer `AzureKeyCredential(api_key)` when `azure_search_api_key` is set; otherwise fall back to `DefaultAzureCredential` (managed identity).

---

## Pipeline Graph (after Phase 09)

```
triage → root_cause → code_context → rag → END
```
