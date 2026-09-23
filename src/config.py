"""统一的模型供应商配置解析。"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Optional, TypedDict

from dotenv import load_dotenv


@dataclass(frozen=True)
class RuntimeConfig:
    """LLM 运行时配置。"""

    provider: str
    api_key: str
    model: str
    base_url: Optional[str] = None
    timeout_seconds: float = 30.0
    max_retries: int = 2


class _ProviderDefaults(TypedDict):
    env_key: str
    base_url: Optional[str]
    model: str


_PROVIDERS: dict[str, _ProviderDefaults] = {
    "deepseek": {
        "env_key": "DEEPSEEK_API_KEY",
        "base_url": "https://api.deepseek.com",
        "model": "deepseek-flash",
    },
    "dashscope": {
        "env_key": "DASHSCOPE_API_KEY",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "model": "qwen-plus",
    },
    "openai": {
        "env_key": "OPENAI_API_KEY",
        "base_url": None,
        "model": "gpt-4o-mini",
    },
}


def _load_openclaw_config(path: Path) -> dict:
    if not path.is_file():
        return {}
    try:
        with path.open("r", encoding="utf-8") as handle:
            value = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def resolve_config(
    environ: Optional[Mapping[str, str]] = None,
    openclaw_path: Optional[Path] = None,
) -> RuntimeConfig:
    """解析一个真正可用于调用的供应商配置。

    优先级：显式 ``BEHAVIOR_PSYCHOLOGY_PROVIDER``，然后按
    DeepSeek、DashScope、OpenAI 顺序寻找可用凭证。环境变量优先于
    ``~/.openclaw/openclaw.json``。
    """

    if environ is None:
        load_dotenv()
    env = dict(os.environ if environ is None else environ)
    config_path = openclaw_path or (Path.home() / ".openclaw" / "openclaw.json")
    file_config = _load_openclaw_config(config_path)
    requested = env.get("BEHAVIOR_PSYCHOLOGY_PROVIDER", "").strip().lower()

    if requested and requested not in _PROVIDERS:
        supported = ", ".join(sorted(_PROVIDERS))
        raise RuntimeError(f"不支持的模型供应商 {requested!r}；可选值：{supported}。")

    candidates = [requested] if requested else ["deepseek", "dashscope", "openai"]
    for provider in candidates:
        defaults = _PROVIDERS[provider]
        env_key = str(defaults["env_key"])
        provider_config = file_config.get(provider, {})
        if not isinstance(provider_config, dict):
            provider_config = {}
        api_key = env.get(env_key, "").strip() or str(provider_config.get("apiKey", "")).strip()
        if not api_key:
            continue

        model = (
            env.get("BEHAVIOR_PSYCHOLOGY_MODEL", "").strip()
            or str(provider_config.get("model", "")).strip()
            or str(defaults["model"])
        )
        base_url = (
            env.get("BEHAVIOR_PSYCHOLOGY_BASE_URL", "").strip()
            or str(provider_config.get("baseUrl", "")).strip()
            or defaults["base_url"]
        )
        try:
            timeout_seconds = float(env.get("BEHAVIOR_PSYCHOLOGY_TIMEOUT_SECONDS", "30"))
            max_retries = int(env.get("BEHAVIOR_PSYCHOLOGY_MAX_RETRIES", "2"))
        except ValueError as exc:
            raise RuntimeError("超时与重试配置必须是数字。") from exc
        if not 1 <= timeout_seconds <= 120:
            raise RuntimeError("BEHAVIOR_PSYCHOLOGY_TIMEOUT_SECONDS 必须在 1-120 秒之间。")
        if not 0 <= max_retries <= 5:
            raise RuntimeError("BEHAVIOR_PSYCHOLOGY_MAX_RETRIES 必须在 0-5 之间。")

        return RuntimeConfig(
            provider=provider,
            api_key=api_key,
            model=model,
            base_url=str(base_url) if base_url else None,
            timeout_seconds=timeout_seconds,
            max_retries=max_retries,
        )

    names = ", ".join(str(v["env_key"]) for v in _PROVIDERS.values())
    raise RuntimeError(
        "配置校验失败：未找到可用的模型凭证。"
        f"请设置以下任一环境变量：{names}，或在 {config_path} 中配置对应供应商。"
    )


def validate_config() -> RuntimeConfig:
    """校验配置并返回解析后的单一事实源。"""

    return resolve_config()
