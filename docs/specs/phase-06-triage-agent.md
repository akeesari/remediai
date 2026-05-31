# Phase 6 — Triage Agent

## Objective

Implement the first LangGraph agent node in the MVP pipeline: the Triage Agent.
It classifies incoming incidents by priority and label, using a fast rule-based path for
known exception types across all supported languages, falling back to the LLM when no rule matches.

> **Language scope:** Rule table covers .NET (MVP), Python (Phase 27), Node.js (Phase 28), Java (future). The rule engine dispatches to the correct language table based on the detected `exception_type` format. Adding a new language requires only a new rule table — no pipeline changes. The
LangGraph pipeline scaffold is established here so every subsequent agent just adds a
new node.

---

## Files to Create

| Path | Purpose |
|------|---------|
| `packages/agent_runtime/triage/__init__.py` | Re-exports `make_triage_node` |
| `packages/agent_runtime/triage/rules.py` | Rule table + `apply_rules()` — no LLM, pure logic |
| `packages/agent_runtime/triage/models.py` | `TriageOutput` Pydantic model — validates LLM JSON |
| `packages/agent_runtime/triage/prompt.py` | `load_triage_prompt()` — reads `docs/prompts/triage_v1.md` |
| `packages/agent_runtime/triage/agent.py` | `make_triage_node(llm)` — LangGraph node factory |
| `packages/agent_runtime/pipeline.py` | `build_pipeline(llm, settings)` — compiles `StateGraph` |
| `apps/worker/agents/runner.py` | `AgentPipelineRunner` — runs pipeline, writes audit log |
| `tests/unit/test_triage_rules.py` | Rule engine unit tests (no LLM) |
| `tests/unit/test_triage_agent.py` | Triage node tests with mocked LLM |
| `tests/integration/test_agent_pipeline.py` | End-to-end pipeline test with mocked LLM |

## Files to Modify

| Path | Change |
|------|--------|
| `packages/agent_runtime/__init__.py` | Export `build_pipeline`, `AgentPipelineRunner` |
| `packages/domain/models/agent_state.py` | Import note: no changes needed for Phase 6 single-node |
| `ROADMAP.md` | Check off triage agent milestone item |

---

## Dependencies

All already declared in `pyproject.toml`:
- `langgraph = "^0.2"` — `StateGraph`, `END`, `CompiledStateGraph`
- `langchain-openai = "^0.2"` — `AzureChatOpenAI`
- `langchain-community` / `langchain-core` — `BaseChatModel`, messages
- `structlog = "^24.2"` — structured logging

---

## Implementation Notes

### Rule Engine (`rules.py`)

Ordered priority table per language. The first matching rule wins; rules with higher severity appear first. The engine selects the correct rule table by detecting the exception type format (e.g., `.NET` uses PascalCase class names; Python uses snake_case or dotted module paths; Node.js uses short type names with message patterns; Java uses fully-qualified class names).

#### .NET Rules (MVP)

| Patterns (substring match on `exception_type`) | Labels | Priority |
|------------------------------------------------|--------|----------|
| OutOfMemoryException, StackOverflowException | resource-exhaustion | critical |
| UnauthorizedAccessException, AuthenticationException, SecurityException | authentication | critical |
| TimeoutException, TaskCanceledException, OperationCanceledException | timeout | high |
| SqlException, DbUpdateException, DbUpdateConcurrencyException | database | high |
| HttpRequestException, WebException, SocketException | network | high |
| NullReferenceException | null-reference | high |
| ArgumentNullException, ArgumentException, ArgumentOutOfRangeException | argument-validation | medium |
| InvalidOperationException | invalid-operation | medium |
| FileNotFoundException, DirectoryNotFoundException, IOException | file-system | medium |
| FormatException, InvalidCastException, OverflowException | data-conversion | medium |
| KeyNotFoundException | missing-key | medium |
| ObjectDisposedException | object-disposed | medium |
| NotImplementedException | not-implemented | low |

#### Python Rules (Phase 27)

| Patterns | Labels | Priority |
|----------|--------|----------|
| MemoryError | resource-exhaustion | critical |
| PermissionError, AuthenticationError, jwt.exceptions | authentication | critical |
| TimeoutError, asyncio.TimeoutError, concurrent.futures.TimeoutError | timeout | high |
| sqlalchemy.exc, psycopg2, pymysql, django.db | database | high |
| ConnectionError, requests.exceptions, httpx | network | high |
| AttributeError, TypeError (None) | null-reference | high |
| ValueError, TypeError | argument-validation | medium |
| FileNotFoundError, IsADirectoryError, IOError | file-system | medium |
| KeyError | missing-key | medium |
| NotImplementedError | not-implemented | low |

#### Node.js / JavaScript Rules (Phase 28)

| Patterns (type + message substring) | Labels | Priority |
|--------------------------------------|--------|----------|
| RangeError, ENOMEM | resource-exhaustion | critical |
| JsonWebTokenError, UnauthorizedError | authentication | critical |
| ETIMEDOUT, ECONNABORTED, AbortError | timeout | high |
| SequelizeError, MongoError, QueryFailedError | database | high |
| ECONNREFUSED, ENOTFOUND, FetchError | network | high |
| TypeError: Cannot read properties of null/undefined | null-reference | high |
| TypeError, RangeError (validation) | argument-validation | medium |
| ENOENT, EISDIR | file-system | medium |
| ReferenceError | missing-key | medium |

#### Java Rules (Future)

| Patterns | Labels | Priority |
|----------|--------|----------|
| java.lang.OutOfMemoryError | resource-exhaustion | critical |
| java.lang.NullPointerException | null-reference | high |
| java.sql.SQLException, org.hibernate | database | high |
| java.net.SocketTimeoutException, java.util.concurrent.TimeoutException | timeout | high |
| java.io.FileNotFoundException, java.io.IOException | file-system | medium |
| java.lang.IllegalArgumentException | argument-validation | medium |
| java.lang.UnsupportedOperationException | not-implemented | low |

If no rule matches, `matched=False` and the node falls through to the LLM.

### Triage Node (`agent.py`)

Node factory pattern: `make_triage_node(llm: BaseChatModel)` returns the async node
function. This keeps the LLM injectable for testing without module-level state.

**Rule path** (rule matches): returns rule result directly, no LLM call, `confidence=1.0`.

**LLM path** (no rule match):
1. Build `[SystemMessage(triage_prompt), HumanMessage(incident_json)]`
2. Call `await llm.ainvoke(messages)`
3. Parse JSON from response, stripping markdown fences if present
4. Validate with `TriageOutput` — invalid priority falls back to `"medium"`
5. On LLM error: set `priority="medium"`, `triage_labels=["unknown"]`,
   `confidence=0.0`, append error to `state["errors"]`

Each invocation appends an `AgentTraceEntry` to `state["agent_trace"]`.

### LangGraph Pipeline (`pipeline.py`)

Phase 6 graph: single node → END.

```
START → triage → END
```

Subsequent phases add `root_cause`, `code_context`, `rag`, `fix_planner`,
`bug_creation` nodes between `triage` and `END`.

`build_pipeline(llm=None, settings=None)` — `llm=None` constructs `AzureChatOpenAI`
from settings; pass a mock for tests.

### Agent Pipeline Runner (`apps/worker/agents/runner.py`)

`AgentPipelineRunner.run(incident)`:
1. Update incident status → `triaging` in PostgreSQL.
2. Build `initial_state: IncidentState` from the `Incident` domain model.
3. Call `await pipeline.ainvoke(initial_state)`.
4. Persist each `agent_trace` entry to `audit_log` table.
5. Update `incidents.priority` from triage output.
6. Flush session (caller commits).

### Audit Log Persistence

`AuditLogOrm` does not have separate `input_summary` / `output_summary` columns; those
are stored in `log_metadata` JSONB alongside `latency_ms`, `prompt_version`, and
`error`.

---

## Acceptance Criteria

- [ ] `pytest tests/unit/test_triage_rules.py -v` — all pass (no LLM)
- [ ] `pytest tests/unit/test_triage_agent.py -v` — all pass (mock LLM)
- [ ] `pytest tests/integration/test_agent_pipeline.py -v` — all pass
- [ ] `ruff check packages/agent_runtime/ apps/worker/agents/` — no errors
- [ ] `mypy packages/agent_runtime/ apps/worker/agents/ --strict` — 0 errors
- [ ] Known exception types use rule path; LLM is never called
- [ ] LLM failure does not raise; incident gets `priority=medium`, error in trace
- [ ] `agent_trace` in final state contains one entry per agent that ran

---

## Commit Message

```
feat(agents): add Triage Agent, LangGraph pipeline scaffold, and AgentPipelineRunner
```
