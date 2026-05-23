from packages.agent_runtime.prompt_registry import get_registry


def load_root_cause_prompt() -> str:
    return get_registry().load("root_cause", "1")
