"""
命令行入口模块：提供简易 CLI 用于本地测试 DefaultBehaviorAnalyzer。

用法示例：
    python -m src.cli --behavior "同事总是最后一个回复我的消息" --subject colleague_A --context "工作群聊"
    python -m src.cli profile --subject colleague_A
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.analyzer import DefaultBehaviorAnalyzer, _load_profiles
from src.schemas import AnalysisRequest


def _format_response_markdown(response) -> str:
    """将 AnalysisResponse 格式化为 Markdown 文本。

    Args:
        response: AnalysisResponse 实例。

    Returns:
        格式化的 Markdown 字符串。
    """
    lines = [
        "# 行为心理分析结果",
        "",
        f"**分析对象**: {response.subject_id or '（未指定）'}",
        f"**置信度**: {response.confidence:.2f}",
        f"**普适性评级**: {response.universality_rating}",
        "",
        "## 行为标签",
    ]

    if response.tags:
        for tag in response.tags:
            lines.append(f"- `{tag}`")
    else:
        lines.append("- 未匹配到显著行为标签")

    lines.extend(["", "## 心理机制"])
    if response.psychological_mechanisms:
        for mech in response.psychological_mechanisms:
            lines.append(f"- **{mech.name}**: {mech.explanation}")
    else:
        lines.append("- 未识别出明确的心理机制")

    lines.extend(["", "## 替代解释"])
    if response.alternative_explanations:
        for idx, alt in enumerate(response.alternative_explanations, 1):
            lines.append(f"{idx}. **{alt.perspective}**")
            lines.append(f"   - {alt.reasoning}")
    else:
        lines.append("- 未找到匹配的替代解释")

    lines.extend(["", "---", "", f"> {response.disclaimer}"])

    return "\n".join(lines)


async def _run_analysis(
    behavior: str,
    subject: Optional[str],
    context: Optional[str],
) -> None:
    """执行分析并打印结果。

    Args:
        behavior: 行为描述文本。
        subject: 分析对象 ID（可选）。
        context: 环境上下文（可选）。
    """
    analyzer = DefaultBehaviorAnalyzer()
    request = AnalysisRequest(
        behavior_description=behavior,
        subject_id=subject,
        context=context,
    )
    response = await analyzer.analyze(request)
    print(_format_response_markdown(response))


def _format_profile_markdown(subject_id: str, profile: Dict[str, Any]) -> str:
    """将画像数据格式化为 Markdown 文本。

    Args:
        subject_id: 对象标识。
        profile: 画像字典。

    Returns:
        格式化的 Markdown 字符串。
    """
    lines: List[str] = [
        f"# 人物画像：{subject_id}",
        "",
        "## 基本信息",
        "",
    ]

    alias = profile.get("alias", "")
    created_at = profile.get("created_at", "")
    updated_at = profile.get("updated_at", "")

    lines.append(f"- **称呼**：{alias or '（未设置）'}")
    lines.append(f"- **首次记录**：{created_at or '（未知）'}")
    lines.append(f"- **最近更新**：{updated_at or '（未知）'}")

    pattern_summary = profile.get("pattern_summary", "")
    recurring_tags = profile.get("recurring_tags", [])
    recurring_mechanisms = profile.get("recurring_mechanisms", [])
    if pattern_summary or recurring_tags or recurring_mechanisms:
        lines.extend(["", "## 模式摘要"])
        if pattern_summary:
            lines.append(f"> {pattern_summary}")
        if recurring_tags:
            lines.append(f"- **高频标签**：{', '.join(recurring_tags)}")
        if recurring_mechanisms:
            lines.append(f"- **重复机制**：{', '.join(recurring_mechanisms)}")
        if not pattern_summary and not recurring_tags and not recurring_mechanisms:
            lines.append("- 暂无足够数据生成模式摘要")

    behavior_history = profile.get("behavior_history", [])
    lines.extend(["", "## 行为历史"])
    if behavior_history:
        lines.append("| 时间 | 行为描述 | 标签 | 机制 | 置信度 | 普适性 |")
        lines.append("|------|----------|------|------|--------|--------|")
        for entry in behavior_history:
            ts = entry.get("timestamp", "")
            desc = entry.get("behavior_description", "")[:40]
            tags = ", ".join(entry.get("tags", []))[:30]
            mechs = ", ".join(entry.get("mechanisms", []))[:30]
            conf = entry.get("confidence", 0.0)
            univ = entry.get("universality_rating", "")
            lines.append(f"| {ts} | {desc} | {tags} | {mechs} | {conf:.2f} | {univ} |")
    else:
        lines.append("- 暂无行为记录")

    lines.append("")
    return "\n".join(lines)


def _run_profile(subject: str) -> None:
    """查询并输出指定对象的画像。

    Args:
        subject: 分析对象 ID。
    """
    from src.analyzer import _ensure_profile_structure

    data = _load_profiles()
    profiles = data.get("profiles", {})
    if subject not in profiles:
        print(f"未找到 ID 为 `{subject}` 的画像记录。", file=sys.stderr)
        sys.exit(1)

    profile = _ensure_profile_structure(profiles[subject])
    print(_format_profile_markdown(subject, profile))


def main() -> None:
    """CLI 主入口函数。

    解析命令行参数，调用分析器，以 Markdown 格式输出结果。
    """
    parser = argparse.ArgumentParser(
        description="行为心理分析 CLI — 基于知识库与 RAG 的行为动机推测工具"
    )
    subparsers = parser.add_subparsers(dest="command", help="可用子命令")

    analyze_parser = subparsers.add_parser("analyze", help="执行行为心理分析")
    analyze_parser.add_argument(
        "--behavior",
        required=True,
        help="用户观察到的行为描述（必填）",
    )
    analyze_parser.add_argument(
        "--subject",
        default=None,
        help="被分析对象的历史人物 ID，用于画像追踪（例如 colleague_A、friend_X）",
    )
    analyze_parser.add_argument(
        "--context",
        default=None,
        help="环境上下文信息，包括时间、地点、触发事件等",
    )

    profile_parser = subparsers.add_parser("profile", help="查询人物画像")
    profile_parser.add_argument(
        "--subject",
        required=True,
        help="被查询对象的历史人物 ID",
    )

    args = parser.parse_args()

    if args.command == "profile":
        try:
            _run_profile(args.subject)
        except Exception as e:
            print(f"未知错误: {e}", file=sys.stderr)
            sys.exit(1)
        return

    if args.command == "analyze" or args.command is None:
        try:
            asyncio.run(_run_analysis(args.behavior, args.subject, args.context))
        except RuntimeError as e:
            print(f"错误: {e}", file=sys.stderr)
            sys.exit(1)
        except Exception as e:
            print(f"未知错误: {e}", file=sys.stderr)
            sys.exit(1)
        return

    parser.print_help()


if __name__ == "__main__":
    main()
