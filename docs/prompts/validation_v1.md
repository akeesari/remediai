# Validation Prompt v1

## Goal

Review a pull request diff for correctness and implementation risk against the
reported root cause and intended recommendation.

## Required Input

- root_cause_summary: string
- recommendation_title: string
- diff: string (unified diff or commit summary text)

## Output Contract

Return JSON only with this shape:

```json
{
  "risk_level": "low",
  "confidence": 0.84,
  "llm_assessment": "The patch adds an explicit null guard that aligns with the identified root cause and avoids broad behavior changes.",
  "reviewer_notes": "Verify edge-case behavior when gateway responses are empty and confirm logs remain actionable.",
  "concerns": [
    "No explicit unit test was added for the null-response path."
  ]
}
```

Constraints:
- risk_level must be one of: low, medium, high.
- confidence must be a float between 0.0 and 1.0.
- llm_assessment should be 2-4 sentences.
- reviewer_notes should provide actionable guidance for a human reviewer.
- concerns should list concrete risks (may be empty).

## Failure Policy

If evidence is insufficient:
- Set risk_level to "medium".
- Set confidence <= 0.5.
- Explain missing evidence in llm_assessment.
- Add explicit follow-up actions in reviewer_notes.

## Safety Rules

- Do not claim certainty when the diff is incomplete.
- Do not infer hidden files or runtime behavior not shown in the diff.
- Do not include unmasked PII in output fields.
