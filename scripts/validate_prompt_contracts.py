from __future__ import annotations

from pathlib import Path

PROMPTS_DIR = Path(__file__).resolve().parents[1] / "docs" / "prompts"
REQUIRED_SECTIONS = [
    "## Goal",
    "## Required Input",
    "## Output Contract",
    "## Failure Policy",
    "## Safety Rules",
]


def _validate_prompt_file(path: Path) -> list[str]:
    errors: list[str] = []
    text = path.read_text(encoding="utf-8")

    for section in REQUIRED_SECTIONS:
        if section not in text:
            errors.append(f"{path}: missing section '{section}'")

    if text.count("```json") < 1:
        errors.append(f"{path}: missing JSON schema block")

    return errors


def main() -> int:
    if not PROMPTS_DIR.exists():
        print(f"prompt directory not found: {PROMPTS_DIR}")
        return 1

    prompt_files = sorted(
        [path for path in PROMPTS_DIR.glob("*_v*.md") if path.name.lower() != "readme.md"]
    )

    if not prompt_files:
        print("no versioned prompt files found")
        return 1

    errors: list[str] = []
    for prompt_path in prompt_files:
        errors.extend(_validate_prompt_file(prompt_path))

    if errors:
        print("prompt contract validation failed")
        for error in errors:
            print(f"- {error}")
        return 1

    print(f"prompt contract validation passed ({len(prompt_files)} files)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
