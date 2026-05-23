# Phase 10 — Fix Planner Agent

## Goal

Generate ranked remediation recommendations from root cause analysis, code snippets, and RAG context. This is the final agent in the analysis pipeline.

## Inputs (from IncidentState)

| Field | Type | Source |
|---|---|---|
| `root_cause_summary` | `str` | root_cause agent |
| `root_cause_json` | `dict` | root_cause agent |
| `code_snippets` | `list[dict]` | code_context agent (up to 3 used) |
| `rag_results` | `list[dict]` | rag agent (up to 5 used) |

## Outputs (written to IncidentState)

| Field | Type | Notes |
|---|---|---|
| `recommendations` | `list[dict]` | 1–3 ranked recommendations |
| `agent_trace` | `list[dict]` | appended entry with `latency_ms` |
| `errors` | `list[str]` | appended on failure |

## Models

### `Recommendation`

```python
class Recommendation(BaseModel):
    rank: int                          # 1-based, consecutive
    title: str                         # short action title
    description: str                   # what to fix and why
    affected_files: list[str]          # file paths
    suggested_change: str              # specific code change hint
    confidence: float                  # clamped to [0, 1]
    source_refs: list[str]             # evidence citations
```

### `FixPlannerOutput`

```python
class FixPlannerOutput(BaseModel):
    recommendations: list[Recommendation]
```

## Processing

1. Build user payload: root_cause_summary, root_cause_json, code_snippets[:3], rag_results[:5]
2. Call LLM with fix_planner_v1.md system prompt
3. Parse JSON response into `FixPlannerOutput`
4. Sort recommendations by confidence descending
5. Limit to top 3; renumber ranks 1, 2, 3
6. On any failure: return default "Gather more diagnostic evidence" (confidence 0.3)

## Failure Behaviour

| Scenario | Result |
|---|---|
| LLM call raises exception | Default recommendation returned; error appended to `errors` |
| JSON parse fails | Same as LLM failure |
| Empty recommendations list | Default recommendation used |

## Pipeline Position

`triage → root_cause → code_context → rag → fix_planner → END`

## Files

```
packages/agent_runtime/fix_planner/
├── __init__.py
├── agent.py          — make_fix_planner_node factory
└── models.py         — Recommendation, FixPlannerOutput

docs/prompts/fix_planner_v1.md   — system prompt
tests/unit/test_fix_planner_agent.py
```
