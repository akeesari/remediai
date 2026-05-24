# PR Patch Prompt v1

## Goal

Refine a natural-language fix suggestion into a complete replacement for the
affected code section, ready to be applied as a file change in Azure DevOps.
Output the full patched file content (not a diff), with the suggested change
applied as precisely as possible.

## Required Input

- file_path: string — relative path of the file to patch
- original_content: string — current content of the file (or the relevant snippet)
- suggested_change: string — natural-language description of the fix to apply

## Output Contract

Return JSON only with this shape:

```json
{
  "patched_content": "// full file content with fix applied\n...",
  "files_changed": ["src/services/OrderService.cs"],
  "change_summary": "Added null guard before dereferencing payment response on line 144."
}
```

Rules:
- patched_content must be the complete, valid file content after the fix.
- files_changed must contain exactly one entry matching file_path.
- change_summary is 1–2 sentences describing exactly what was changed.
- If the suggested_change cannot be safely applied, return patched_content identical
  to original_content and note the issue in change_summary.

## Failure Policy

If the fix cannot be determined from the input:
- Return patched_content unchanged (identical to original_content).
- Set change_summary to explain why the fix could not be applied.
- Do not invent changes not derivable from suggested_change.

## Safety Rules

- Never remove error handling, logging, or authentication checks.
- Do not introduce new dependencies or namespace changes.
- Apply only the minimal change described in suggested_change.
- Do not include unmasked PII in any output field.
