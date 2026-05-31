# Root Cause Prompt v2

## Goal

Produce a concise root-cause explanation and structured JSON breakdown from
exception evidence.  v2 requires a fully qualified `component` method path
(e.g., `OrderService.CompleteCheckout`) and adds an `affected_module` field
to distinguish throw site from root cause module/namespace.

This prompt is **language-agnostic**. It handles .NET, Python, Node.js, Java, and any
other language. Stack trace format and naming conventions vary by language — reason
from the evidence provided without assuming a specific language unless the exception
type or stack trace clearly indicates one.

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
  "root_cause_summary": "Null reference in OrderService.completeCheckout occurs when the payment client returns null and the result is dereferenced without a guard.",
  "root_cause_json": {
    "component": "OrderService.completeCheckout",
    "likely_cause": "Missing null guard before dereferencing payment client response.",
    "contributing_factors": ["No nullability check", "Async result not awaited correctly"],
    "confidence": 0.85,
    "affected_module": "app.services.orders"
  },
  "evidence": [
    "Top frame points to OrderService.completeCheckout",
    "Exception type indicates a null dereference"
  ]
}
```

Rules:
- `root_cause_summary`: 1 to 4 sentences
- `root_cause_json.component`: fully qualified method path in the language's native format:
  - .NET: `ClassName.MethodName`
  - Python: `module.ClassName.method_name` or `function_name`
  - Node.js: `ClassName.methodName` or `functionName`
  - Java: `com.example.ClassName.methodName`
- `root_cause_json.confidence`: float in [0, 1]
- `root_cause_json.affected_module`: the module/namespace/package of the affected component in the language's native format (C# namespace, Python module path, Java package, Node.js file path without extension); empty string if unknown
- `evidence`: 1 to 5 entries

## Failure Policy

When evidence is insufficient:
- set likely_cause to "insufficient_evidence"
- set component to the top stack frame method name if available, else "unknown"
- include missing evidence notes in evidence
- set confidence below 0.5
- set `affected_module` to empty string

## Safety Rules

- Keep explanation factual and evidence-based.
- Never invent file paths or methods not present in input.
- Do not include unmasked PII in any output field.
- component must reference only methods visible in the provided stack trace.
