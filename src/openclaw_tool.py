"""
OpenClaw 插件适配层：将 DefaultBehaviorAnalyzer 注册为 OpenClaw Agent 生态中的 Tool。

规范说明：
- register_tools() 返回工具元数据列表，供 OpenClaw 在启动时扫描注册。
- handle_tool_call() 为异步处理函数，接收 tool_name 与 arguments，返回 dict 结果。
- 额外配置从 ~/.openclaw/openclaw.json 读取（如自定义模型、温度参数等）。
"""

import asyncio
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.analyzer import DefaultBehaviorAnalyzer
from src.schemas import AnalysisRequest, validate_config

# ── OpenClaw 配置读取 ─────────────────────────────────────────────

OPENCLAW_CONFIG_PATH = Path.home() / ".openclaw" / "openclaw.json"


def _load_openclaw_config() -> Dict[str, Any]:
    """读取 OpenClaw 用户配置文件，返回配置字典。

    若文件不存在或解析失败，返回空字典。
    """
    if not OPENCLAW_CONFIG_PATH.exists():
        return {}
    try:
        with open(OPENCLAW_CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


# ── 工具元数据定义 ────────────────────────────────────────────────

# 复用 Function Calling JSON Schema 定义工具参数
_TOOL_PARAMETERS = {
    "type": "object",
    "properties": {
        "behavior_description": {
            "type": "string",
            "description": "用户描述的行为文本，包含观察到的具体行为、言语或社交互动场景。必填。",
        },
        "subject_id": {
            "type": "string",
            "description": "被分析对象的历史人物 ID，用于长期追踪与画像关联（例如 colleague_A、friend_X）。可选。",
        },
        "context": {
            "type": "string",
            "description": "环境上下文信息，包括时间、地点、触发事件、在场人员、关系背景等。可选。",
        },
        "request_id": {
            "type": "string",
            "description": "请求追踪 ID，用于链路追踪、日志关联与幂等性控制。可选。",
        },
    },
    "required": ["behavior_description"],
}

_TOOL_METADATA = {
    "name": "analyzing-behavior",
    "description": (
        "分析用户描述的行为或社交互动，识别可能的心理机制、认知模式与社会因素。"
        "提供结构化分析报告，包含替代解释、普适性评级与置信度分数。"
        "适用于'帮我分析一下...'、'为什么TA会...'、'你怎么看这件事...'等场景。"
        "明确不是诊断工具，不输出人格障碍或临床标签。"
    ),
    "parameters": _TOOL_PARAMETERS,
}

# ── 全局分析器实例（延迟初始化） ──────────────────────────────────

_analyzer_instance: Optional[DefaultBehaviorAnalyzer] = None


def _get_analyzer() -> DefaultBehaviorAnalyzer:
    """获取 DefaultBehaviorAnalyzer 单例实例。

    首次调用时执行初始化（包含配置校验与知识库加载）。
    """
    global _analyzer_instance
    if _analyzer_instance is None:
        validate_config()
        _analyzer_instance = DefaultBehaviorAnalyzer()
    return _analyzer_instance


# ── OpenClaw 规范接口 ─────────────────────────────────────────────


def register_tools() -> List[Dict[str, Any]]:
    """注册工具列表。

    OpenClaw Agent 在启动时会调用此函数，扫描并注册返回的工具元数据。

    Returns:
        工具元数据列表，每个元素包含 name、description、parameters。
    """
    return [_TOOL_METADATA]


async def handle_tool_call(tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """处理 OpenClaw 发起的工具调用。

    Args:
        tool_name: 被调用的工具名称。
        arguments: 工具参数字典，需符合 _TOOL_PARAMETERS 定义的 Schema。

    Returns:
        分析结果的 JSON 字典（由 AnalysisResponse.model_dump() 生成）。

    Raises:
        ValueError: 当 tool_name 不匹配或参数非法时抛出。
        RuntimeError: 当分析器执行失败时抛出。
    """
    if tool_name != _TOOL_METADATA["name"]:
        raise ValueError(f"未知工具: {tool_name}。本插件仅支持 {_TOOL_METADATA['name']}。")

    behavior_description = arguments.get("behavior_description", "")
    if not behavior_description:
        raise ValueError("参数 'behavior_description' 不能为空。")

    # 读取 OpenClaw 额外配置（当前预留扩展点，如自定义模型、温度等）
    openclaw_cfg = _load_openclaw_config()
    _ = openclaw_cfg  # 预留：未来可用于覆盖默认模型参数

    analyzer = _get_analyzer()

    request = AnalysisRequest(
        behavior_description=behavior_description,
        subject_id=arguments.get("subject_id") or None,
        context=arguments.get("context") or None,
        request_id=arguments.get("request_id") or None,
    )

    response = await analyzer.analyze(request)
    return response.model_dump()


# ── 独立测试入口 ──────────────────────────────────────────────────


async def _test() -> None:
    """内部测试函数：模拟一次 OpenClaw 工具调用。"""
    print("=" * 60)
    print("OpenClaw Tool 独立测试入口")
    print("=" * 60)

    print("\n【注册工具】")
    tools = register_tools()
    for tool in tools:
        print(f"  - {tool['name']}: {tool['description'][:60]}...")

    print("\n【模拟调用】")
    test_args = {
        "behavior_description": "同事在会议中总是沉默，但私下会发很长的消息补充观点",
        "subject_id": "colleague_A",
        "context": "团队周会，讨论新项目分工",
    }
    print(f"参数: {json.dumps(test_args, ensure_ascii=False, indent=2)}")

    try:
        result = await handle_tool_call("analyzing-behavior", test_args)
        print("\n【返回结果】")
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except Exception as e:
        print(f"\n【错误】{e}")

    print("\n" + "=" * 60)
    print("测试结束")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(_test())
