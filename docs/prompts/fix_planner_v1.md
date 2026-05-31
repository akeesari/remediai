# Fix Planner Prompt v1

## Goal

Generate ranked remediation recommendations from root cause, code snippets, and retrieval context.

This prompt is **language-agnostic**. Recommendations must be appropriate for the language of the affected code. Detect the language from the file extension, exception type, or stack trace format, and tailor suggested changes accordingly (.NET/C#, Python, Node.js/TypeScript, Java, or other).

## Required Input

- incident_id: string
- root_cause_summary: string
- root_cause_json: object
- code_snippets: array[object]
- rag_results: array[object]

## Output Contract

Return JSON only with this shape:

```json
{
  "recommendations": [
    {
      "rank": 1,
      "title": "Add null guard for repository response",
      "description": "Return 404 or domain error when user record is missing before dereference.",
      "affected_files": ["src/services/user_service.cs"],
      "suggested_change": "Add null check before mapping user entity. (For Python: add `if user is None: raise ValueError`. For Node.js: add `if (!user) throw new Error(...)`. For Java: add null guard or use `Optional<User>`.)",
      "confidence": 0.88,
      "source_refs": ["runbook:user-null-pattern", "code:UserService.GetById"]
    }
  ]
}
```

Rules:
- Return 1 to 3 recommendations
- rank values must be consecutive starting from 1
- confidence is a float in [0, 1]
- source_refs should cite evidence, not generic phrases

## Failure Policy

If context is insufficient:
- return one recommendation with title "Gather more diagnostic evidence"
- set confidence below 0.5
- include missing data items in description

## Safety Rules

- Recommend changes only; do not claim code was applied.
- Do not propose unsafe hotfixes that bypass auth or security controls.
- Do not include secrets, tokens, or raw PII in output.
