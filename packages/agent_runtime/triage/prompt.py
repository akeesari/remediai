from packages.agent_runtime.prompt_registry import get_registry


def load_triage_prompt() -> str:
    return get_registry().load("triage", "1")
