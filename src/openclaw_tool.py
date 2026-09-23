"""OpenClaw 工具适配层。"""

from __future__ import annotations

from typing import Any, Optional

from src.analyzer import DefaultBehaviorAnalyzer
from src.config import validate_config
from src.schemas import AnalysisRequest

_TOOL_METADATA = {
    "name": "analyzing-behavior",
    "description": (
        "根据有限观察整理多种非诊断行为假设。默认不保存画像；"
        "persist_profile=true 时必须提供匿名 subject_id 与稳定 request_id。"
    ),
    "parameters": AnalysisRequest.model_json_schema(),
}

_analyzer_instance: Optional[DefaultBehaviorAnalyzer] = None


def _get_analyzer() -> DefaultBehaviorAnalyzer:
    global _analyzer_instance
    if _analyzer_instance is None:
        config = validate_config()
        _analyzer_instance = DefaultBehaviorAnalyzer(config=config)
    return _analyzer_instance


def register_tools() -> list[dict[str, Any]]:
    return [_TOOL_METADATA]


async def handle_tool_call(tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    if tool_name != _TOOL_METADATA["name"]:
        raise ValueError(f"未知工具：{tool_name}")
    request = AnalysisRequest.model_validate(arguments)
    response = await _get_analyzer().analyze(request)
    return response.model_dump(mode="json")
