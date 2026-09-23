"""Shared offline test doubles."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from src.analyzer import DefaultBehaviorAnalyzer
from src.config import RuntimeConfig
from src.profile_store import ProfileStore


class FakeCompletions:
    def __init__(self, content: str = "{}", error: Exception | None = None) -> None:
        self.content = content
        self.error = error
        self.calls: list[dict] = []

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        message = SimpleNamespace(content=self.content)
        return SimpleNamespace(choices=[SimpleNamespace(message=message)])


class FakeClient:
    def __init__(self, content: str = "{}", error: Exception | None = None) -> None:
        self.completions = FakeCompletions(content, error)
        self.chat = SimpleNamespace(completions=self.completions)
        self.closed = False

    async def close(self) -> None:
        self.closed = True


@pytest.fixture
def runtime_config() -> RuntimeConfig:
    return RuntimeConfig(
        provider="deepseek",
        api_key="test-key",
        model="test-model",
        base_url="https://example.invalid",
    )


@pytest.fixture
def analyzer_factory(tmp_path, runtime_config):
    def factory(content: str = "{}", error: Exception | None = None):
        client = FakeClient(content, error)
        store = ProfileStore(tmp_path / "profiles.json")
        analyzer = DefaultBehaviorAnalyzer(config=runtime_config, client=client, profile_store=store)
        return analyzer, client, store

    return factory
