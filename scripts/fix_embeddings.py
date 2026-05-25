#!/usr/bin/env python3
"""
案例 embedding 修复脚本。

使用 openai.AsyncOpenAI 调用 text-embedding-3-small 模型，
为 cases.json 中所有案例生成真实语义向量。

支持 --dry-run 参数用于预览，不实际修改文件。
"""

import argparse
import asyncio
import json
import logging
import os
import sys
from pathlib import Path

logger = logging.getLogger("fix_embeddings")


def _get_openai_api_key() -> str:
    key = os.environ.get("OPENAI_API_KEY", "")
    if not key:
        config_path = Path.home() / ".openclaw" / "openclaw.json"
        if config_path.exists():
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                    key = cfg.get("openai", {}).get("apiKey", "")
            except Exception:
                pass
    return key


async def _generate_embedding(client, text: str, model: str = "text-embedding-3-small") -> list:
    response = await client.embeddings.create(model=model, input=text)
    return response.data[0].embedding


async def main() -> None:
    parser = argparse.ArgumentParser(description="为 cases.json 生成真实 embedding 向量")
    parser.add_argument("--dry-run", action="store_true", help="预览模式，不保存修改")
    parser.add_argument("--model", default="text-embedding-3-small", help="embedding 模型")
    parser.add_argument("--verbose", action="store_true", help="输出详细日志")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="[%(asctime)s] %(levelname)s: %(message)s",
    )

    kb_dir = Path(__file__).parent.parent / "knowledge_base"
    cases_path = kb_dir / "cases.json"

    with open(cases_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    api_key = _get_openai_api_key()
    if not api_key:
        logger.error("未检测到可用的 OpenAI API Key。请设置 OPENAI_API_KEY 环境变量。")
        sys.exit(1)

    try:
        from openai import AsyncOpenAI
    except ImportError as e:
        logger.error(f"openai SDK 未安装: {e}")
        sys.exit(1)

    client = AsyncOpenAI(api_key=api_key)

    cases = data.get("cases", [])
    if not cases:
        logger.info("案例库为空，无需处理。")
        return

    fixed_count = 0
    skipped_count = 0

    for case in cases:
        case_id = case.get("id", "unknown")
        desc = case.get("user_description", "")

        if not desc:
            logger.warning(f"案例 {case_id} 缺少 user_description，跳过。")
            skipped_count += 1
            continue

        if args.dry_run:
            logger.info(f"[DRY-RUN] 将为 {case_id} 生成 embedding: {desc[:60]}...")
            fixed_count += 1
            continue

        try:
            embedding = await _generate_embedding(client, desc, model=args.model)
            case["embedding"] = embedding
            logger.info(f"已生成 {case_id} 的 embedding: dimension={len(embedding)}")
            fixed_count += 1
        except Exception as e:
            logger.error(f"生成 {case_id} 的 embedding 失败: {e}")
            skipped_count += 1

    if not args.dry_run:
        with open(cases_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.info(f"已保存 cases.json。")

    logger.info(f"\n处理完成: 成功 {fixed_count} 条, 跳过/失败 {skipped_count} 条")
    if args.dry_run:
        logger.info("本次为预览模式，未实际修改文件。")


if __name__ == "__main__":
    asyncio.run(main())
