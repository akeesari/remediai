# Triage Prompt v2

## Goal

Assign incident priority, labels, affected service, and optional grouping signal
using exception data.  v2 adds explicit `service_name` extraction from stack
trace file paths and an `affected_service` output field.

This prompt is **language-agnostic**. It handles .NET, Python, Node.js, Java, and any
other language. Reason from the exception type and stack trace without assuming a
specific language unless the evidence clearly indicates one.

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
  "priority": "high",
  "triage_labels": ["null-reference", "order-service"],
  "group_id": null,
  "rationale": "NullReferenceException in OrderService indicates missing null guard on repository result.",
  "confidence": 0.88,
  "affected_service": "OrderService"
}
```

Rules:
- priority is one of: critical, high, medium, low
- triage_labels is a non-empty list of lowercase strings
- group_id is null or UUID string
- confidence is a float in [0, 1]
- `affected_service` is the top-level service inferred from stack trace file paths; null if undetermined. Examples by language:
  - .NET: `src/services/OrderService.cs` → `OrderService`
  - Python: `src/services/order_service.py` → `order_service`
  - Node.js: `src/services/OrderService.ts` → `OrderService`
  - Java: `src/main/java/com/example/services/OrderService.java` → `OrderService`

## Failure Policy

If evidence is weak or conflicting, return:
- priority as medium
- at least one generic label, such as unknown
- confidence below 0.5
- rationale that states the uncertainty
- affected_service as null

## Safety Rules

- Do not include raw emails, IP addresses, access tokens, or usernames in rationale.
- If PII appears in source input, replace with placeholders such as [EMAIL], [IP], [USERNAME].
- Never fabricate service names not visible in the stack trace paths.
