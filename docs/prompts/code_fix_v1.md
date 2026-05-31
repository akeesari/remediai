# Code Fix Prompt v1

## Goal

Generate a precise, minimal code fix for a known exception.  You will receive
the **complete file content** and a natural-language description of the required
change.  Return the **complete fixed file content** with only the necessary
change applied.

## Required Input

- `exception_type` — the exception class that was raised
- `root_cause_summary` — one-paragraph root cause analysis
- `file_path` — relative path of the file to fix
- `original_content` — current complete content of the file
- `recommendation_title` — short title of the approved fix
- `recommendation_description` — detailed description of what to fix and why
- `suggested_change` — specific code change to apply

## Output Contract

Return JSON only — no markdown fences, no commentary outside the JSON:

```json
{
  "patched_content": "<complete file content after fix applied>",
  "change_summary": "Added null guard on line 42 before dereferencing payment response.",
  "confidence": 0.92
}
```

### Field Rules

- `patched_content` — the **complete**, syntactically valid file after the fix.
  Must include every line of the original file that was not changed.
  Must not be a diff, a snippet, or a fragment.
- `change_summary` — 1–2 sentences describing exactly what line(s) changed and why.
- `confidence` — float in [0, 1] reflecting how certain you are the fix is correct
  given the available context.  Use 0.0 when the fix cannot be safely applied.

## Safety Rules

1. Apply **only** the minimal change described in `suggested_change`.
   Do not refactor, rename, reformat, or clean up unrelated code.
2. Never remove or weaken error handling, logging, authentication, or
   authorisation checks.
3. Do not introduce new imports, dependencies, or namespace changes unless
   `suggested_change` explicitly requires them.
4. If the fix cannot be safely applied (ambiguous location, conflicting logic,
   insufficient context):
   - Return `patched_content` **identical** to `original_content`.
   - Set `confidence` to `0.0`.
   - Explain why in `change_summary`.
5. Do not include PII, secrets, tokens, or passwords in any output field.

## Failure Policy

When in doubt, return the original content unchanged rather than applying a
speculative or incorrect fix.  A PR created with an unchanged file is safer
than one with a broken change — the Validation Agent and human reviewer will
catch remaining issues.
