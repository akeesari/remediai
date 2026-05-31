# Phase 18 — Validation Agent: PR Diff Review

## Goal

After the PR Agent creates a draft PR, the Validation Agent fetches the diff,
runs static and syntactic safety checks, and calls the LLM to assess correctness
and risk. The validation report is attached to the PR description and stored in
the incident record so the human reviewer has a structured risk summary.

### Phase 18 Update (Gap 2 — Real Static Analysis)

Phase 35 introduced the `code_fix_result` field in `IncidentState` which contains
`patched_content` — the complete patched file produced by the Code Fix Agent.
This update uses that content to run **language-aware syntax validation** and
**import analysis** without LLM involvement or shell execution:

- **Python**: `ast.parse()` — real syntax check, not a heuristic
- **All languages**: bracket/brace balance validation
- **All languages**: new external import detection in the diff

These checks run before the LLM call and can block the PR independently of LLM
confidence.

---

## Background

AGENT_DESIGN.md §8 defines the Validation Agent as the final Phase 2 pipeline
node.  It runs after the PR Agent sets `pr_url` and `pr_branch` in state.

---

## Deliverables

| Artifact | Description |
|---|---|
| `packages/agent_runtime/validation_agent/agent.py` | `make_validation_agent_node(ado_client, llm)` factory |
| `packages/agent_runtime/validation_agent/models.py` | `ValidationReport`, `ValidationCheck` Pydantic models |
| `packages/agent_runtime/validation_agent/static_checks.py` | Static diff safety checks + language-aware build/test file detection (Phase 36) |
| `packages/agent_runtime/validation_agent/syntax_checks.py` | **New (Gap 2)**: language-aware syntax validation using `ast.parse()` for Python; bracket balance for others |
| `packages/integrations/ado/pr_reader.py` | `get_pr_diff(repo, pr_id)` — fetches unified diff from ADO REST API |
| Updated `packages/agent_runtime/pipeline.py` | Wire Validation Agent after PR Agent |
| Updated `packages/domain/models/agent_state.py` | Add `validation_report` field |
| `docs/prompts/validation_v1.md` | LLM prompt for diff correctness and risk assessment |
| `tests/unit/test_validation_agent.py` | Unit tests for node, static checks, and mock LLM |
| `tests/unit/test_static_checks.py` | Dedicated tests for static checker edge cases |
| `tests/unit/test_syntax_checks.py` | **New (Gap 2)**: syntax validation tests |

---

## Pipeline Position

```
pr_agent → validation_agent → END
```

The Validation Agent only runs when `pr_url` is set in state (i.e., the PR
Agent succeeded).  If `pr_url` is `None`, this node is a no-op.

---

## Validation Agent Logic

```
1. Guard: if state["pr_url"] is None, return state unchanged.
2. Fetch the PR diff via pr_reader.get_pr_diff().
3. Extract patched_content and language from state["code_fix_result"] and state["exception_language"].
4. Run static checks on the diff (secrets, size, TODOs, scope, test deletion, build files).
5. Run syntax checks on patched_content (ast.parse for Python; bracket balance for others).
6. If any check is FAIL severity, skip LLM and set overall_status = "blocked".
7. Otherwise, call LLM (validation_v1) with the diff + root_cause_summary.
8. Parse LLM response into ValidationReport.
9. Append validation report summary to the PR description via ADO PRs PATCH API.
10. Write validation_report to state.
```

---

## `ValidationReport` Model

```python
class ValidationCheck(BaseModel):
    check_name: str
    status: Literal["pass", "warn", "fail"]
    detail: str

class ValidationReport(BaseModel):
    overall_status: Literal["approved", "needs_review", "blocked"]
    checks: list[ValidationCheck]
    llm_assessment: str          # 2–4 sentence LLM summary
    risk_level: Literal["low", "medium", "high"]
    confidence: float
    reviewer_notes: str          # Actionable guidance for the human reviewer
```

`overall_status`:
- `"approved"` — all checks pass, LLM confidence ≥ 0.75, risk_level = low.
- `"needs_review"` — some warnings or medium risk; human must still review.
- `"blocked"` — one or more FAIL checks; PR should not be merged without manual override.

---

## Static Checks (`static_checks.py`)

These checks run on the **diff text** — pure string analysis, no external calls.

| Check | Severity | Condition |
|---|---|---|
| `no_secrets` | FAIL | Diff contains patterns matching secrets (API keys, connection strings, passwords) |
| `diff_size` | WARN | Total lines changed > 200 |
| `diff_size` | FAIL | Total lines changed > 500 |
| `no_new_todos` | WARN | Diff introduces `TODO` or `FIXME` comments |
| `single_file` | WARN | More than 3 files changed (unexpected scope) |
| `no_test_deletion` | FAIL | Language-appropriate test file has deletions (Phase 36: all languages) |
| `no_build_file_change` | WARN | Language-appropriate build file modified (Phase 36: all languages) |
| `no_new_imports` | WARN | Diff introduces new import/using/require statements (possible new dependency) |

## Syntax Checks (`syntax_checks.py`) — Gap 2 Addition

These checks run on the **full patched file content** from `code_fix_result` — not
the diff. They validate the generated code is syntactically correct before human review.

| Check | Severity | Condition | Method |
|---|---|---|---|
| `syntax_valid` | FAIL | Patched file has a syntax error | Python: `ast.parse()`; others: bracket balance |
| `bracket_balance` | WARN | Patched file has unbalanced `{}`/`[]`/`()` | Pure string counting |

**No shell execution.** `ast.parse()` is a Python standard library call. No subprocess,
no `dotnet build`, no `tsc`. For non-Python languages the check is heuristic but catches
the most common code-generation mistakes (mismatched braces).

---

## Prompt: `docs/prompts/validation_v1.md`

The validation prompt receives:
- `root_cause_summary` — the original diagnosis.
- `recommendation_title` — what was intended.
- `diff` — the unified diff (truncated to 300 lines if larger).

The LLM responds with structured JSON:
```json
{
  "risk_level": "low | medium | high",
  "confidence": 0.0–1.0,
  "llm_assessment": "...",
  "reviewer_notes": "...",
  "concerns": ["..."]
}
```

---

## PR Description Update

After validation, the PR description is updated with a validation summary block:

```markdown
---
## RemediAI Validation Report

**Status:** ✅ Approved / ⚠️ Needs Review / 🚫 Blocked
**Risk:** Low / Medium / High  
**Confidence:** 82%

### Checks
- ✅ No secrets detected
- ✅ Diff size within limits
- ⚠️ 2 TODO comments introduced

### Assessment
{llm_assessment}

### Reviewer Notes
{reviewer_notes}

*Generated by RemediAI Validation Agent — human review required before merge.*
```

---

## PII Scrubbing

The Validation Agent calls an LLM (`validation_v1`).  Before building
`user_content` in `_call_llm()`, apply `scrub()` to fields that originate
from incident state:

```python
from packages.integrations.pii_scrubber import scrub

user_content = json.dumps({
    "root_cause_summary": scrub(state.get("root_cause_summary", "") or ""),
    "recommendation_title": scrub(recommendation_title),
    "diff": diff_text,   # source code diff — exempt per Phase 15 spec
})
```

Add `log.debug("pii_scrub_applied", fields_scrubbed=["root_cause_summary", "recommendation_title"])`.

---

## Audit Trail

Write an `AgentTraceEntry` to `state["agent_trace"]`.  The `output_summary`
should record `overall_status` and `risk_level`.

---

## Unit Test Requirements

### `test_validation_agent.py`

| Test | Asserts |
|---|---|
| `test_no_pr_url_skips_validation` | Node is no-op when `pr_url` is None |
| `test_all_checks_pass_status_approved` | `overall_status == "approved"` when LLM confident + no issues |
| `test_secret_in_diff_blocks` | `overall_status == "blocked"` when `no_secrets` check fails |
| `test_large_diff_warns` | WARN check present when diff > 200 lines |
| `test_validation_report_written_to_state` | `state["validation_report"]` populated |

### `test_static_checks.py`

| Test | Asserts |
|---|---|
| `test_detects_api_key_in_diff` | `no_secrets` → FAIL |
| `test_clean_diff_passes_all` | All checks PASS |
| `test_test_file_deletion_fails` | `no_test_deletion` → FAIL |
| `test_large_diff_over_500_fails` | `diff_size` → FAIL |
| `test_large_diff_200_500_warns` | `diff_size` → WARN |

---

## Acceptance Criteria

- `ruff check .` and `mypy apps/ packages/ --strict` pass.
- All existing tests continue to pass.
- Validation Agent is a no-op when no PR URL is present.
- A diff containing a secret pattern produces `overall_status = "blocked"`.
- Validation report is appended to the ADO PR description.
- `state["validation_report"]` is populated in the full pipeline run.

---

## Out of Scope

- Automated PR merge even when validation passes (humans always merge).
- Full compilation (`dotnet build`, `tsc --noEmit`, `javac`) — requires shell execution.
- Running the test suite against the patch — requires a CI environment.
- Custom check plugin system.
