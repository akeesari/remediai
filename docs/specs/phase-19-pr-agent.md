# Phase 19 — PR Agent: Branch, Patch & Draft PR

## Goal

After a human approves a fix recommendation (Phase 20 gate), the PR Agent
creates a feature branch, applies the suggested code change as a patch, and
opens a **draft** pull request in Azure DevOps Repos for human review.  The
PR is never auto-completed.

---

## Background

SPEC.md FR-11 and AGENT_DESIGN.md §7 define the PR Agent as a Phase 2
capability.  The PR Agent only runs when an explicit approval event is
recorded in the database (enforced by the human approval gate in Phase 20).

---

## Deliverables

| Artifact | Description |
|---|---|
| `packages/agent_runtime/pr_agent/agent.py` | `make_pr_agent_node(ado_client)` factory |
| `packages/agent_runtime/pr_agent/models.py` | `PRAgentOutput` Pydantic model |
| `packages/agent_runtime/pr_agent/patch_builder.py` | `build_patch(snippet, suggested_change)` — generates a unified diff |
| `packages/integrations/ado/repos_writer.py` | `create_branch()`, `push_patch()`, `create_pull_request()` on ADO Repos |
| Updated `packages/agent_runtime/pipeline.py` | Wire PR Agent node after Bug Creator (conditional edge on `approval_status`) |
| Updated `packages/domain/models/agent_state.py` | Add `pr_branch`, `pr_url`, `approval_status` fields to `IncidentState` |
| `tests/unit/test_pr_agent.py` | Unit tests for node + patch builder |
| `tests/unit/test_repos_writer.py` | Unit tests for ADO Repos writer with mock HTTP |
| `docs/prompts/pr_patch_v1.md` | Prompt asking LLM to refine suggested_change into a valid code patch |

---

## Pipeline Integration

The PR Agent is added as a **conditional node** after `bug_creator`.  The
routing function checks `state["approval_status"]`:

```
bug_creator → [approval_status == "approved"] → pr_agent → END
             [approval_status != "approved"] → END
```

This means:
- Incidents without approval skip the PR Agent and terminate after Bug Creator
  (current MVP behaviour is preserved).
- Incidents with `approval_status = "approved"` proceed to the PR Agent.

---

## PR Agent Logic

```
1. Validate: recommendations list non-empty; approved_recommendation_rank set.
2. Select the approved recommendation from state["recommendations"].
3. Call LLM (pr_patch_v1) to refine suggested_change into a well-formed code patch.
4. Create branch: remedia/{incident_id[:8]}/{recommendation.rank}
   branched from the default branch (usually main).
5. Apply patch to affected_files via ADO Repos push API.
6. Create draft PR:
   - Title:       [RemediAI] {recommendation.title}
   - Description: root_cause_summary + recommendation.description + disclaimer
   - Source:      remedia/... branch
   - Target:      default branch
   - Draft:       true
   - Auto-complete: never set
7. Write pr_branch and pr_url to state.
8. Update WorkItemOrm.pr_url in PostgreSQL.
```

---

## `PRAgentOutput` Model

```python
class PRAgentOutput(BaseModel):
    pr_branch: str
    pr_url: str
    pr_id: int
    patch_applied: bool
    files_changed: list[str]
```

---

## `IncidentState` Additions

```python
approval_status: str | None          # None | "approved" | "rejected"
approved_recommendation_rank: int | None
pr_branch: str | None
pr_url: str | None
```

---

## ADO Repos Writer

`packages/integrations/ado/repos_writer.py`:

| Method | Description |
|---|---|
| `create_branch(repo, branch_name, from_ref)` | Creates a Git ref via ADO Refs API |
| `push_patch(repo, branch, file_path, content, commit_message)` | Pushes a single file change via ADO Push API |
| `create_pull_request(repo, source_branch, target_branch, title, description, is_draft)` | Creates a PR via ADO PRs API; returns PR ID and URL |

Authentication: PAT from settings (existing `azure_devops_pat` setting).

---

## Prompt: `docs/prompts/pr_patch_v1.md`

The patch prompt receives:
- `file_path` — the file to change.
- `original_content` — the current file content (fetched via ADO Repos read).
- `suggested_change` — the Fix Planner's free-text suggestion.

The LLM outputs a **unified diff** (`--- a/file`, `+++ b/file` format) that
can be applied programmatically.  The prompt instructs the model to:
- Make the minimal change required.
- Preserve surrounding code style.
- Output only the diff, no explanation.

---

## Safety Constraints

- The PR Agent may only write to the repository configured in
  `azure_devops_repository` setting.
- Branch names are prefixed `remedia/` and scoped to the incident ID.
- Draft status is hardcoded — no code path sets auto-complete.
- If the patch cannot be applied cleanly (merge conflict), the agent sets
  `patch_applied = False`, writes an error to `state.errors`, and still
  creates the PR with a note in the description for the reviewer.
- Max diff size: 500 lines changed.  Larger diffs are rejected with an error.

---

## Unit Test Requirements

### `test_pr_agent.py`

| Test | Asserts |
|---|---|
| `test_approved_incident_creates_branch` | `create_branch` called with correct naming pattern |
| `test_approved_incident_creates_draft_pr` | PR created with `is_draft=True` |
| `test_pr_url_written_to_state` | `state["pr_url"]` non-empty after node run |
| `test_unapproved_incident_skips_pr` | Node not called when `approval_status != "approved"` |
| `test_patch_too_large_sets_error` | Error appended when diff exceeds 500 lines |

### `test_repos_writer.py`

| Test | Asserts |
|---|---|
| `test_create_branch_calls_correct_endpoint` | PUT to `/refs` with correct ref name |
| `test_push_patch_calls_push_api` | POST to `/pushes` with file content |
| `test_create_pull_request_draft` | `isDraft: true` in request payload |

---

## Acceptance Criteria

- `ruff check .` and `mypy apps/ packages/ --strict` pass.
- All existing tests continue to pass.
- Incidents without approval skip the PR Agent (pipeline regression test).
- Incidents with `approval_status = "approved"` trigger branch + PR creation.
- PRs are never set to auto-complete in any code path.
