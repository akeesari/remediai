from __future__ import annotations

import re

from packages.agent_runtime.validation_agent.models import ValidationCheck

_SECRET_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("api_key", re.compile(r"(?i)(api[_-]?key|apikey)\s*[:=]\s*['\"]?[a-z0-9_\-]{12,}")),
    (
        "connection_string",
        re.compile(r"(?i)(connection\s*string|Server=.+;Database=.+;(?:User Id|Password)=.+;)"),
    ),
    ("password", re.compile(r"(?i)password\s*[:=]\s*['\"].+['\"]")),
    (
        "azure_secret",
        re.compile(r"(?i)AccountKey=|SharedAccessSignature=|sig=[A-Za-z0-9%\-_]{10,}"),
    ),
]


def run_static_checks(diff_text: str) -> list[ValidationCheck]:
    checks: list[ValidationCheck] = []
    checks.append(_check_no_secrets(diff_text))
    checks.append(_check_diff_size(diff_text))
    checks.append(_check_no_new_todos(diff_text))
    checks.append(_check_single_file_scope(diff_text))
    checks.append(_check_no_test_deletion(diff_text))
    checks.append(_check_no_build_file_change(diff_text))
    return checks


def has_fail_checks(checks: list[ValidationCheck]) -> bool:
    return any(check.status == "fail" for check in checks)


def _check_no_secrets(diff_text: str) -> ValidationCheck:
    for label, pattern in _SECRET_PATTERNS:
        if pattern.search(diff_text):
            return ValidationCheck(
                check_name="no_secrets",
                status="fail",
                detail=f"Potential secret pattern detected: {label}.",
            )
    return ValidationCheck(
        check_name="no_secrets",
        status="pass",
        detail="No obvious secrets detected.",
    )


def _changed_line_count(diff_text: str) -> int:
    count = 0
    for line in diff_text.splitlines():
        if line.startswith("+++") or line.startswith("---"):
            continue
        if line.startswith("+") or line.startswith("-"):
            count += 1
    return count


def _check_diff_size(diff_text: str) -> ValidationCheck:
    changed_lines = _changed_line_count(diff_text)
    if changed_lines > 500:
        return ValidationCheck(
            check_name="diff_size",
            status="fail",
            detail=f"Diff has {changed_lines} changed lines (limit 500).",
        )
    if changed_lines > 200:
        return ValidationCheck(
            check_name="diff_size",
            status="warn",
            detail=f"Diff has {changed_lines} changed lines; review scope carefully.",
        )
    return ValidationCheck(
        check_name="diff_size",
        status="pass",
        detail=f"Diff size is {changed_lines} changed lines.",
    )


def _check_no_new_todos(diff_text: str) -> ValidationCheck:
    todo_lines = [
        line
        for line in diff_text.splitlines()
        if line.startswith("+")
        and not line.startswith("+++")
        and ("TODO" in line or "FIXME" in line)
    ]
    if todo_lines:
        return ValidationCheck(
            check_name="no_new_todos",
            status="warn",
            detail=f"Found {len(todo_lines)} new TODO/FIXME comments.",
        )
    return ValidationCheck(
        check_name="no_new_todos",
        status="pass",
        detail="No new TODO/FIXME comments introduced.",
    )


def _diff_file_paths(diff_text: str) -> list[str]:
    paths: list[str] = []
    for line in diff_text.splitlines():
        if line.startswith("diff --git "):
            parts = line.split()
            if len(parts) >= 4:
                b_path = parts[3]
                if b_path.startswith("b/"):
                    paths.append(b_path[2:])
    return paths


def _check_single_file_scope(diff_text: str) -> ValidationCheck:
    files = _diff_file_paths(diff_text)
    file_count = len(set(files))
    if file_count > 3:
        return ValidationCheck(
            check_name="single_file",
            status="warn",
            detail=f"Diff modifies {file_count} files; expected focused patch.",
        )
    return ValidationCheck(
        check_name="single_file",
        status="pass",
        detail=f"Diff modifies {file_count} file(s).",
    )


def _check_no_test_deletion(diff_text: str) -> ValidationCheck:
    current_path = ""
    deleted_lines = 0
    test_path_pattern = re.compile(r"(?i)test[s]?\.cs$")

    for line in diff_text.splitlines():
        if line.startswith("diff --git "):
            parts = line.split()
            current_path = parts[2][2:] if len(parts) >= 3 and parts[2].startswith("a/") else ""
            continue
        if not test_path_pattern.search(current_path):
            continue
        if line.startswith("-") and not line.startswith("---"):
            deleted_lines += 1

    if deleted_lines > 0:
        return ValidationCheck(
            check_name="no_test_deletion",
            status="fail",
            detail=f"Detected {deleted_lines} deleted line(s) in test files.",
        )
    return ValidationCheck(
        check_name="no_test_deletion",
        status="pass",
        detail="No test file deletions detected.",
    )


def _check_no_build_file_change(diff_text: str) -> ValidationCheck:
    files = _diff_file_paths(diff_text)
    build_files = [path for path in files if path.endswith(".csproj") or path.endswith(".sln")]
    if build_files:
        return ValidationCheck(
            check_name="no_build_file_change",
            status="warn",
            detail=f"Build files modified: {', '.join(sorted(set(build_files)))}.",
        )
    return ValidationCheck(
        check_name="no_build_file_change",
        status="pass",
        detail="No build project files modified.",
    )
