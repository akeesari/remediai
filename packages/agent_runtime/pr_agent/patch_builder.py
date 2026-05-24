from __future__ import annotations

import difflib

_MAX_DIFF_LINES = 500


class PatchTooLargeError(ValueError):
    """Raised when a generated diff exceeds the maximum allowed size."""


def build_patch(original: str, patched: str, file_path: str) -> str:
    """Generate a unified diff between *original* and *patched* content.

    Raises ``PatchTooLargeError`` if the diff exceeds ``_MAX_DIFF_LINES`` lines.
    Returns an empty string when original and patched are identical (no-op patch).
    """
    original_lines = original.splitlines(keepends=True)
    patched_lines = patched.splitlines(keepends=True)

    diff = list(
        difflib.unified_diff(
            original_lines,
            patched_lines,
            fromfile=f"a/{file_path}",
            tofile=f"b/{file_path}",
            lineterm="",
        )
    )

    if len(diff) > _MAX_DIFF_LINES:
        raise PatchTooLargeError(
            f"Diff is {len(diff)} lines which exceeds the {_MAX_DIFF_LINES}-line limit."
        )

    return "\n".join(diff)
