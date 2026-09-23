"""命令行入口。"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import uuid
from typing import Any, Optional

from src.analyzer import DefaultBehaviorAnalyzer
from src.profile_store import ProfileStore
from src.schemas import AnalysisRequest, AnalysisResponse


def _format_response_markdown(response: AnalysisResponse) -> str:
    lines = ["# 行为假设分析结果", ""]
    if response.blocked:
        lines.extend(
            [
                f"**安全边界**：{response.safety_category or 'boundary'}",
                "",
                response.alternative_explanations[0].reasoning,
                "",
                f"> {response.disclaimer}",
            ]
        )
        return "\n".join(lines)

    lines.extend(
        [
            f"**模型估计置信度**：{response.confidence:.2f}（未经统计校准）",
            f"**普适性评级**：{response.universality_rating}",
            "",
            "## 行为标签",
        ]
    )
    lines.extend([f"- `{tag}`" for tag in response.tags] or ["- 未生成可靠标签"])
    lines.extend(["", "## 可能的心理机制"])
    if response.psychological_mechanisms:
        for mechanism in response.psychological_mechanisms:
            lines.append(
                f"- **{mechanism.name}**（{mechanism.universality_rating}，"
                f"模型估计 {mechanism.confidence:.2f}）：{mechanism.explanation}"
            )
    else:
        lines.append("- 未生成可靠机制")
    lines.extend(["", "## 替代解释"])
    for index, alternative in enumerate(response.alternative_explanations, 1):
        lines.append(f"{index}. **{alternative.perspective}**：{alternative.reasoning}")
    lines.extend(["", "## 局限"])
    lines.extend(f"- {item}" for item in response.limitations)
    if response.pattern_summary:
        lines.extend(["", "## 已同意保存的画像摘要", response.pattern_summary])
    if response.subject_id:
        status = "已保存" if response.profile_persisted else "未新增记录"
        lines.extend(["", f"**匿名对象 ID**：`{response.subject_id}`；画像状态：{status}"])
    if response.degradation_flags:
        lines.extend(["", f"**降级标记**：{', '.join(response.degradation_flags)}"])
    lines.extend(["", "---", "", f"> {response.disclaimer}"])
    return "\n".join(lines)


async def _run_analysis(args: argparse.Namespace) -> None:
    analyzer = DefaultBehaviorAnalyzer()
    try:
        request_id = args.request_id
        if args.save_profile and not request_id:
            request_id = str(uuid.uuid4())
        request = AnalysisRequest(
            behavior_description=args.behavior,
            subject_id=args.subject,
            context=args.context,
            request_id=request_id,
            persist_profile=args.save_profile,
        )
        response = await analyzer.analyze(request)
        if args.json:
            print(response.model_dump_json(indent=2))
        else:
            print(_format_response_markdown(response))
    finally:
        await analyzer.close()


def _format_profile_markdown(subject_id: str, profile: dict[str, Any]) -> str:
    lines = [f"# 本地画像：{subject_id}", "", "> 仅包含用户曾显式同意保存的观察。", ""]
    lines.extend(
        [
            f"- **创建时间**：{profile.get('created_at', '未知')}",
            f"- **更新时间**：{profile.get('updated_at', '未知')}",
            f"- **记录数**：{len(profile.get('behavior_history', []))}",
        ]
    )
    if profile.get("pattern_summary"):
        lines.extend(["", "## 摘要", profile["pattern_summary"]])
    lines.extend(["", "## 历史记录"])
    for entry in profile.get("behavior_history", []):
        lines.extend(
            [
                f"- `{entry.get('request_id', 'legacy')}` · {entry.get('timestamp', '')}",
                f"  - 行为：{entry.get('behavior_description', '')}",
                f"  - 标签：{', '.join(entry.get('tags', [])) or '无'}",
            ]
        )
    if not profile.get("behavior_history"):
        lines.append("- 暂无记录")
    return "\n".join(lines)


def _profile_or_exit(store: ProfileStore, subject: str) -> dict[str, Any]:
    profile = store.get(subject)
    if profile is None:
        raise RuntimeError(f"未找到匿名对象 ID {subject!r} 的画像。")
    return profile


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="行为假设分析 CLI（非诊断工具）")
    subparsers = parser.add_subparsers(dest="command", required=True)

    analyze_parser = subparsers.add_parser("analyze", help="分析一段可观察行为")
    analyze_parser.add_argument("--behavior", required=True, help="可观察到的行为描述")
    analyze_parser.add_argument("--context", default=None, help="已脱敏的情境信息")
    analyze_parser.add_argument("--subject", default=None, help="匿名对象 ID")
    analyze_parser.add_argument("--request-id", default=None, help="稳定请求 ID，用于幂等")
    analyze_parser.add_argument(
        "--save-profile",
        action="store_true",
        help="明确同意把本次观察保存到本机画像；必须同时提供 --subject",
    )
    analyze_parser.add_argument("--json", action="store_true", help="输出 JSON")

    profile_parser = subparsers.add_parser("profile", help="查看本地画像")
    profile_parser.add_argument("--subject", required=True)
    profile_parser.add_argument("--json", action="store_true")

    export_parser = subparsers.add_parser("export-profile", help="导出本地画像 JSON")
    export_parser.add_argument("--subject", required=True)

    forget_parser = subparsers.add_parser("forget-entry", help="按 request_id 删除一条画像记录")
    forget_parser.add_argument("--subject", required=True)
    forget_parser.add_argument("--request-id", required=True)
    forget_parser.add_argument("--yes", action="store_true", help="确认删除")

    delete_parser = subparsers.add_parser("delete-profile", help="删除一个本地画像")
    delete_parser.add_argument("--subject", required=True)
    delete_parser.add_argument("--yes", action="store_true", help="确认删除")
    return parser


def main(argv: Optional[list[str]] = None) -> None:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "analyze":
            asyncio.run(_run_analysis(args))
            return

        store = ProfileStore()
        if args.command in {"profile", "export-profile"}:
            profile = _profile_or_exit(store, args.subject)
            if args.command == "export-profile" or args.json:
                print(json.dumps(profile, ensure_ascii=False, indent=2))
            else:
                print(_format_profile_markdown(args.subject, profile))
            return

        if not args.yes:
            raise RuntimeError("删除操作需要显式传入 --yes。")
        if args.command == "forget-entry":
            changed = store.forget_entry(args.subject, args.request_id)
            print("已删除指定记录。" if changed else "未找到指定记录。")
            return
        if args.command == "delete-profile":
            changed = store.delete(args.subject)
            print("已删除画像。" if changed else "未找到画像。")
            return
    except Exception as exc:
        print(f"错误：{exc}", file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
