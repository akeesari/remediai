# Phase 18 — RAG & Code Context Quality Hardening

## Goal

Improve the relevance of RAG retrieval results and code context snippets so
that Fix Planner recommendations are more precise and actionable.  Quality is
measured against the agent eval harness introduced in Phase 13.

---

## Background

The current RAG agent issues a simple keyword query built from the root cause
summary.  The code context agent fetches the top stack frame file verbatim.
Both produce generic results when:

- The root cause summary contains broad language ("service layer failure").
- Stack frames reference internal framework code rather than application code.
- The search index returns documents ranked only by BM25 score, ignoring
  exception type affinity.

This phase adds hybrid search, query rewriting, result re-ranking, and
smarter frame selection to the code context agent.

---

## Deliverables

| Artifact | Description |
|---|---|
| `packages/agent_runtime/rag/query_builder.py` | `build_search_query(state)` — structured query from state fields |
| `packages/agent_runtime/rag/reranker.py` | `rerank(results, state)` — post-retrieval re-ranking by source type + exception affinity |
| Updated `packages/agent_runtime/rag/agent.py` | Use `build_search_query` and `reranker`; enable hybrid search |
| Updated `packages/agent_runtime/code_context/frame_filter.py` | Smarter application-frame selection with namespace allow/deny lists |
| `docs/prompts/triage_v2.md` | Refined triage prompt requesting explicit component identification |
| `docs/prompts/root_cause_v2.md` | Refined root cause prompt requesting structured component path |
| Updated `packages/agent_runtime/prompt_registry.py` | Registry already handles versioning; agents updated to load `v2` |
| Updated `tests/agent-evals/test_agent_evals.py` | New eval assertions for RAG result count and recommendation quality signals |
| Updated agent eval fixtures | Add `rag_results_min_count` and `recommendation_confidence_min` fields |

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
2. **Vector query**: the full `root_cause_summary` sentence (richer semantic signal).
3. **Filter**: prefer `exception_type` matches in `prior_fix` documents first.
4. **Hybrid mode**: both keyword and vector sub-queries submitted in one request.

---

## Result Re-ranker

`rerank(results: list[RAGResult], state: IncidentState) -> list[RAGResult]`:

Scoring factors (weighted sum, normalised to 0–1):

| Factor | Weight | Description |
|---|---|---|
| Azure AI Search score | 0.5 | Raw relevance from hybrid search |
| Source type priority | 0.3 | `prior_fix=1.0 > runbook=0.75 > documentation=0.5 > source_code=0.25` |
| Exception type affinity | 0.2 | +1.0 if document `exception_type` matches current `exception_type`; else 0 |

Return top 5 re-ranked results with `relevance_score` set to the weighted sum.

---

## Code Context Frame Filter

Replace the current "top frame only" logic with:

1. **Deny list**: skip frames matching known framework prefixes:
   - `Microsoft.AspNetCore.*`
   - `System.*`
   - `lambda_method*`
2. **Allow list priority**: frames whose file path starts with the
   configured `ado_source_path_prefix` (`src/`) ranked first.
3. **Limit**: top 5 application frames after filtering.
4. **Fallback**: if all frames are in the deny list, take the top 3 regardless.

---

## Prompt Versioning

### `docs/prompts/root_cause_v2.md`

Additions over v1:
- Require the LLM to populate `component` as a fully qualified method path
  (e.g., `OrderService.CompleteCheckout`) rather than a class name.
- Add `affected_namespace` field to `root_cause_json`.
- Instruct the model to distinguish between the throw site and the root cause.

### `docs/prompts/triage_v2.md`

Additions over v1:
- Require explicit `service_name` extraction from the stack trace file paths.
- Add `affected_service` to the triage output.

Agents default to loading `v2` for these two prompts after this phase.
`v1` remains available in the registry for rollback.

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

Add corresponding assertions in `test_agent_evals.py`:
- `result["rag_results"]` length ≥ `expected["rag_results_min_count"]`.
- All recommendations have `confidence` ≥ `expected["recommendation_confidence_min"]`.
- `result["root_cause_json"]["component"]` is non-empty.

---

## Acceptance Criteria

- `ruff check .` and `mypy apps/ packages/ --strict` pass.
- All 285+ existing tests pass (v1 prompts still work; agents now load v2).
- New eval assertions pass against updated fixtures with mocked search results.
- Re-ranker unit tests: given mixed source types, `prior_fix` results appear first.
- Frame filter unit tests: framework frames excluded; application frames retained.

---

## Out of Scope

- Fine-tuning the embedding model.
- Custom reranker model training.
- Automated A/B testing of prompt versions in production.
