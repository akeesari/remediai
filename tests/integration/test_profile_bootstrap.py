from __future__ import annotations

from types import SimpleNamespace

from packages.agent_runtime.pipeline import build_pipeline


def test_build_pipeline_bootstraps_portable_profile_with_stub_llm() -> None:
    settings = SimpleNamespace(
        remediai_profile="portable",
        llm_provider_id="stub-chat",
    )

    pipeline = build_pipeline(settings=settings)

    assert pipeline is not None
