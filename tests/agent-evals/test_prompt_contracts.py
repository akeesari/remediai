from __future__ import annotations

from pathlib import Path

PROMPTS_DIR = Path(__file__).resolve().parents[2] / "docs" / "prompts"
REQUIRED_PROMPTS = ["triage_v1.md", "root_cause_v1.md", "fix_planner_v1.md"]
REQUIRED_SECTIONS = [
    "## Goal",
    "## Required Input",
    "## Output Contract",
    "## Failure Policy",
    "## Safety Rules",
]


def test_required_prompt_contracts_exist() -> None:
    for prompt_name in REQUIRED_PROMPTS:
        prompt_path = PROMPTS_DIR / prompt_name
        assert prompt_path.exists(), f"missing prompt contract: {prompt_path}"


def test_prompt_contract_sections_and_json_examples() -> None:
    for prompt_name in REQUIRED_PROMPTS:
        prompt_path = PROMPTS_DIR / prompt_name
        content = prompt_path.read_text(encoding="utf-8")

        for section in REQUIRED_SECTIONS:
            assert section in content, f"{prompt_name} missing section {section}"

        assert "```json" in content, f"{prompt_name} must contain a JSON example block"
