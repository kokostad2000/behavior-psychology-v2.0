from __future__ import annotations

import json

import pytest

from src.config import resolve_config


@pytest.mark.parametrize(
    ("env_name", "provider", "model"),
    [
        ("DEEPSEEK_API_KEY", "deepseek", "deepseek-flash"),
        ("DASHSCOPE_API_KEY", "dashscope", "qwen-plus"),
        ("OPENAI_API_KEY", "openai", "gpt-4o-mini"),
    ],
)
def test_each_provider_key_resolves(env_name, provider, model, tmp_path) -> None:
    config = resolve_config({env_name: "test-key"}, tmp_path / "missing.json")
    assert config.provider == provider
    assert config.model == model


def test_openclaw_provider_config_is_used(tmp_path) -> None:
    path = tmp_path / "openclaw.json"
    path.write_text(json.dumps({"deepseek": {"apiKey": "file-key", "model": "deepseek-flash"}}))
    config = resolve_config({}, path)
    assert config.provider == "deepseek"
    assert config.api_key == "file-key"


def test_unknown_provider_fails(tmp_path) -> None:
    with pytest.raises(RuntimeError, match="不支持"):
        resolve_config({"BEHAVIOR_PSYCHOLOGY_PROVIDER": "unknown"}, tmp_path / "missing")
