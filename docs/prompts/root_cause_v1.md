# Root Cause Prompt v1

## Goal

Produce a concise root-cause explanation and structured JSON breakdown from exception evidence.

## Required Input

- incident_id: string
- exception_type: string
- exception_message: string
- stack_trace: string
- triage_labels: array[string]
- top_stack_frames: array[string]

## Output Contract

Return JSON only with this shape:

```json
{
  "root_cause_summary": "Null reference in UserService.GetById occurs when repository returns no row and null is dereferenced.",
  "root_cause_json": {
    "component": "UserService.GetById",
    "likely_cause": "Missing null guard before using repository result.",
    "contributing_factors": ["No nullability test", "Unvalidated data assumption"],
    "confidence": 0.82
  },
  "evidence": [
    "Top frame points to UserService.GetById",
    "Exception is System.NullReferenceException"
  ]
}
```

Rules:
- root_cause_summary length: 1 to 4 sentences
- root_cause_json.confidence is a float in [0, 1]
- evidence has 1 to 5 entries

## Failure Policy

When evidence is insufficient:
- set likely_cause to "insufficient_evidence"
- include missing evidence notes in evidence
- set confidence below 0.5

## Safety Rules

- Keep explanation factual and evidence-based.
- Never invent file paths or methods not present in input.
- Do not include unmasked PII in any output field.
