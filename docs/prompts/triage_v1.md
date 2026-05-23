# Triage Prompt v1

## Goal

Assign incident priority, labels, and optional grouping signal using exception data.

## Required Input

- incident_id: string
- exception_type: string
- exception_message: string
- stack_trace: string
- recent_incident_signatures: array[string]

## Output Contract

Return JSON only with this shape:

```json
{
  "priority": "critical",
  "triage_labels": ["timeout", "database"],
  "group_id": null,
  "rationale": "Timeout exceptions increased 4x in 30 minutes and affect login path.",
  "confidence": 0.86
}
```

Rules:
- priority is one of: critical, high, medium, low
- triage_labels is a non-empty list of lowercase strings
- group_id is null or UUID string
- confidence is a float in [0, 1]

## Failure Policy

If evidence is weak or conflicting, return:
- priority as medium
- at least one generic label, such as unknown
- confidence below 0.5
- rationale that states the uncertainty

## Safety Rules

- Do not include raw emails, IP addresses, access tokens, or usernames in rationale.
- If PII appears in source input, replace with placeholders such as [EMAIL], [IP], [USERNAME].
