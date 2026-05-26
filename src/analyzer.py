"""
核心分析器模块：实现 DefaultBehaviorAnalyzer，基于 LLM 直接推理的心理分析工作流。

工作流：输入解析 → LLM 推理 → 结果组装 → 画像更新
"""

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from openai import AsyncOpenAI

load_dotenv()

from src.interfaces import BehaviorAnalyzer
from src.schemas import (
    AnalysisRequest,
    AnalysisResponse,
    _AlternativeExplanation,
    _PsychologicalMechanism,
)

# ── Paths ─────────────────────────────────────────────────────────

SKILL_DIR = Path(__file__).parent.parent
KB_DIR = SKILL_DIR / "knowledge_base"
PATTERNS_PATH = KB_DIR / "behavior_patterns.json"
MECHANISMS_PATH = KB_DIR / "psychological_mechanisms.json"
ALTERNATIVES_PATH = KB_DIR / "alternative_explanations.json"
PROFILES_PATH = KB_DIR / "user_profiles.json"


# ── Config Helpers ───────────────────────────────────────────────


def _get_dashscope_key() -> str:
    """获取 DashScope API Key，优先环境变量，其次配置文件。"""
    key = os.environ.get("DASHSCOPE_API_KEY", "")
    if key:
        return key
    config_path = Path.home() / ".openclaw" / "openclaw.json"
    if config_path.exists():
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
                key = cfg.get("dashscope", {}).get("apiKey", "")
        except Exception:
            pass
    return key


def _get_fallback_key() -> str:
    """获取备用 API Key（DeepSeek / OpenAI），用于兼容场景。"""
    key = os.environ.get("DEEPSEEK_API_KEY", "")
    if not key:
        key = os.environ.get("OPENAI_API_KEY", "")
    if not key:
        config_path = Path.home() / ".openclaw" / "openclaw.json"
        if config_path.exists():
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                    key = cfg.get("deepseek", {}).get("apiKey", "")
                    if not key:
                        key = cfg.get("openai", {}).get("apiKey", "")
            except Exception:
                pass
    return key


def _get_api_base_url() -> str:
    """获取 API Base URL，若配置了 DeepSeek Key 则返回 DeepSeek 地址。"""
    if os.environ.get("DEEPSEEK_API_KEY", ""):
        return "https://api.deepseek.com"
    config_path = Path.home() / ".openclaw" / "openclaw.json"
    if config_path.exists():
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
                if cfg.get("deepseek", {}).get("apiKey", ""):
                    return "https://api.deepseek.com"
        except Exception:
            pass
    return ""


def validate_config() -> None:
    """校验运行时配置，确保 AI 接入凭证可用。

    检查以下任一凭证：
    1. 环境变量 DASHSCOPE_API_KEY（优先，用于 LLM 推理）
    2. 环境变量 OPENAI_API_KEY 或 DEEPSEEK_API_KEY
    3. 配置文件 ~/.openclaw/openclaw.json

    若均不可用，抛出 RuntimeError 并提供友好的中文报错信息。
    """
    dashscope_key = os.getenv("DASHSCOPE_API_KEY", "").strip()
    openai_key = os.getenv("OPENAI_API_KEY", "").strip()
    deepseek_key = os.getenv("DEEPSEEK_API_KEY", "").strip()
    openclaw_config_path = os.path.expanduser("~/.openclaw/openclaw.json")
    openclaw_readable = os.path.isfile(openclaw_config_path) and os.access(openclaw_config_path, os.R_OK)

    has_valid_key = False
    if dashscope_key or openai_key or deepseek_key:
        has_valid_key = True
    elif openclaw_readable:
        try:
            with open(openclaw_config_path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
                if (
                    cfg.get("dashscope", {}).get("apiKey", "").strip()
                    or cfg.get("openai", {}).get("apiKey", "").strip()
                    or cfg.get("deepseek", {}).get("apiKey", "").strip()
                ):
                    has_valid_key = True
        except Exception:
            pass

    if not has_valid_key:
        raise RuntimeError(
            "配置校验失败：未检测到可用的 AI 接入凭证。\n"
            "请至少设置以下一项：\n"
            "  1) 环境变量 DASHSCOPE_API_KEY（推荐，用于通义千问推理）\n"
            "  2) 环境变量 OPENAI_API_KEY 或 DEEPSEEK_API_KEY\n"
            "  3) 可读的配置文件 ~/.openclaw/openclaw.json\n"
            "两者均不可用时，系统无法继续运行。"
        )


# ── Knowledge Base Loaders ───────────────────────────────────────


def _load_json(path: Path) -> Dict[str, Any]:
    """加载指定路径的 JSON 文件。

    Args:
        path: JSON 文件路径。

    Returns:
        解析后的 Python 字典。
    """
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


# ── Profile Management ───────────────────────────────────────────


def _load_profiles() -> Dict[str, Any]:
    """加载用户画像数据，支持旧版结构自动迁移。"""
    if not PROFILES_PATH.exists():
        return {"version": "2.0", "profiles": {}}
    with open(PROFILES_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    data.setdefault("version", "2.0")
    data.setdefault("profiles", {})
    return data


def _save_profiles(data: Dict[str, Any]) -> None:
    """原子化保存用户画像数据：先写入临时文件，再替换目标文件。"""
    import tempfile

    tmp_path = PROFILES_PATH.with_suffix(".tmp")
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp_path, PROFILES_PATH)


def _migrate_profile(profile: Dict[str, Any]) -> Dict[str, Any]:
    """将旧版画像结构迁移到新版结构。

    旧版字段：relationship, first_analyzed, last_analyzed, analysis_count,
              recurring_tags, recurring_mechanisms, user_notes,
              confidence_trend, history
    新版字段：subject_id, alias, created_at, updated_at,
              behavior_history, pattern_summary
    """
    import datetime

    now = datetime.datetime.now().isoformat()
    migrated: Dict[str, Any] = {
        "subject_id": profile.get("subject_id", ""),
        "alias": profile.get("alias", ""),
        "created_at": profile.get("created_at", profile.get("first_analyzed", now)),
        "updated_at": profile.get("updated_at", profile.get("last_analyzed", now)),
        "behavior_history": [],
        "pattern_summary": "",
    }

    old_history = profile.get("history", [])
    old_confidence_trend = profile.get("confidence_trend", [])
    old_recurring_tags = profile.get("recurring_tags", [])
    old_recurring_mechanisms = profile.get("recurring_mechanisms", [])

    if old_history:
        for idx, entry in enumerate(old_history):
            migrated["behavior_history"].append({
                "timestamp": entry.get("timestamp", now),
                "behavior_description": entry.get("behavior_description", ""),
                "tags": entry.get("tags", []),
                "mechanisms": entry.get("mechanisms", []),
                "confidence": entry.get("confidence", 0.0),
                "universality_rating": "",
            })

    # 旧版 recurring 数据在新版中通过 _generate_pattern_summary 重新生成
    analysis_count = profile.get("analysis_count", len(old_history))
    if analysis_count:
        migrated["_legacy_analysis_count"] = analysis_count
    if old_confidence_trend:
        migrated["_legacy_confidence_trend"] = old_confidence_trend

    return migrated


def _ensure_profile_structure(profile: Dict[str, Any]) -> Dict[str, Any]:
    """确保画像字典包含新版所有字段，缺失时自动补全。"""
    if "behavior_history" not in profile:
        profile = _migrate_profile(profile)
    profile.setdefault("subject_id", "")
    profile.setdefault("alias", "")
    profile.setdefault("created_at", "")
    profile.setdefault("updated_at", "")
    profile.setdefault("behavior_history", [])
    # pattern_summary 在新版中为字符串类型
    if "pattern_summary" not in profile or isinstance(profile.get("pattern_summary"), dict):
        profile["pattern_summary"] = ""
    return profile


def _get_or_create_profile(subject_id: str, alias: str = "") -> Dict[str, Any]:
    """获取或创建指定人物的画像条目。

    Args:
        subject_id: 人物标识。
        alias: 用户对该对象的称呼。

    Returns:
        该人物的画像字典（新版结构）。
    """
    import datetime

    data = _load_profiles()
    profiles = data.setdefault("profiles", {})

    if subject_id not in profiles:
        now = datetime.datetime.now().isoformat()
        profiles[subject_id] = {
            "subject_id": subject_id,
            "alias": alias,
            "created_at": now,
            "updated_at": now,
            "behavior_history": [],
            "pattern_summary": "",
        }
        _save_profiles(data)

    profile = profiles[subject_id]
    profile = _ensure_profile_structure(profile)
    profiles[subject_id] = profile
    return profile


def _generate_pattern_summary(profile: Dict[str, Any]) -> tuple[str, list[str], list[str]]:
    """根据 behavior_history 自动生成行为模式摘要文本及重复标签/机制列表。

    统计规则：
    1. 取最近 5 条历史记录（不足则取全部）。
    2. 统计出现频次 >= 2 的重复标签和重复机制。
    3. 若重复项 >= 2 个，生成结构化摘要。
    4. 若重复项不足 2 个，返回观察建议文本。

    Args:
        profile: 用户画像字典，包含 behavior_history 列表。

    Returns:
        tuple: (summary_text, recurring_tags, recurring_mechanisms)
    """
    from collections import Counter

    history = profile.get("behavior_history", [])
    if not history:
        return "", [], []

    recent_history = history[-5:]

    tag_counter: Counter = Counter()
    mech_counter: Counter = Counter()
    for entry in recent_history:
        for tag in entry.get("tags", []):
            tag_counter[tag] += 1
        for mech in entry.get("mechanisms", []):
            mech_counter[mech] += 1

    repeated_tags = [tag for tag, count in tag_counter.items() if count >= 2]
    repeated_mechs = [mech for mech, count in mech_counter.items() if count >= 2]

    repeated_items = repeated_tags + repeated_mechs

    if len(repeated_items) >= 2:
        tags_text = "、".join(repeated_tags) if repeated_tags else ""
        mechs_text = "、".join(repeated_mechs) if repeated_mechs else ""
        parts: list[str] = []
        if tags_text:
            parts.append(f"该对象在近期互动中反复表现出 {tags_text} 等行为模式")
        if mechs_text:
            parts.append(f"常见潜在机制包括 {mechs_text}")
        summary = "，".join(parts) + "。需注意这些模式可能受情境因素影响，并非稳定人格特质。"
        return summary, repeated_tags, repeated_mechs
    else:
        return "该对象近期行为模式未呈现明显重复规律，建议继续观察积累更多数据。", [], []


def _check_boundary_violation(text: str) -> bool:
    """检查输入文本是否触发边界拦截规则。

    拦截规则（任一命中即拦截）：
    - 临床诊断请求关键词
    - 法律/责任判定关键词
    - 自伤/自杀/虐待关键词

    Args:
        text: 用户输入的行为描述文本。

    Returns:
        若命中任一拦截规则返回 True，否则返回 False。
    """
    clinical_keywords = [
        "诊断", "人格障碍", "NPD", "BPD", "抑郁症", "焦虑症",
        "精神分裂", "PTSD", "OCD", "心理疾病", "mental disorder", "DSM",
    ]
    legal_keywords = [
        "违法", "犯罪", "判刑", "责任认定", "法律", "证据", "起诉",
    ]
    crisis_keywords = [
        "自杀", "自残", "伤害自己", "虐待", "abuse", "self-harm",
    ]

    text_lower = text.lower()
    for kw in clinical_keywords + legal_keywords + crisis_keywords:
        if kw.lower() in text_lower:
            return True
    return False


def _update_profile(
    subject_id: str,
    tags: List[str],
    mechanisms: List[_PsychologicalMechanism],
    confidence: float,
    universality_rating: str,
    request: AnalysisRequest,
) -> None:
    """将本次分析结果追加到人物画像的历史记录中，并在条件满足时刷新 pattern_summary。

    Args:
        subject_id: 人物标识。
        tags: 本次匹配的行为标签。
        mechanisms: 本次识别的心理机制。
        confidence: 本次分析的置信度。
        universality_rating: 本次分析的普适性评级。
        request: 原始分析请求。
    """
    import datetime

    data = _load_profiles()
    profiles = data.setdefault("profiles", {})

    if subject_id not in profiles:
        return

    profile = profiles[subject_id]
    profile = _ensure_profile_structure(profile)

    profile["updated_at"] = datetime.datetime.now().isoformat()
    if not profile.get("created_at"):
        profile["created_at"] = profile["updated_at"]

    history = profile.get("behavior_history", [])
    history.append({
        "timestamp": datetime.datetime.now().isoformat(),
        "behavior_description": request.behavior_description,
        "tags": tags,
        "mechanisms": [m.name for m in mechanisms],
        "confidence": confidence,
        "universality_rating": universality_rating,
    })
    if len(history) > 50:
        history = history[-50:]
    profile["behavior_history"] = history

    # 设计依据：至少需要 3 条历史记录才生成模式摘要。
    # 1-2 条记录的统计样本过小，容易产生偶然性结论；
    # 3 条及以上才能观察到初步的重复标签与机制趋势，
    # 同时避免过早给用户贴上不稳定的模式标签。
    # 若之前已生成过摘要（pattern_summary 为字符串且非空），仅追加新记录，不重新生成。
    if len(history) >= 3:
        existing_summary = profile.get("pattern_summary", "")
        if not isinstance(existing_summary, str) or not existing_summary.strip():
            summary, recurring_tags, recurring_mechanisms = _generate_pattern_summary(profile)
            profile["pattern_summary"] = summary
            profile["recurring_tags"] = recurring_tags
            profile["recurring_mechanisms"] = recurring_mechanisms

    profiles[subject_id] = profile
    _save_profiles(data)


# ── DefaultBehaviorAnalyzer ──────────────────────────────────────


class DefaultBehaviorAnalyzer(BehaviorAnalyzer):
    """默认行为心理分析器实现。

    基于 LLM 直接推理的工作流：输入解析 → LLM 推理 → 结果组装 → 画像更新。
    """

    def __init__(self) -> None:
        """初始化分析器。

        执行以下步骤：
        1. 调用 validate_config() 校验配置（API Key 等）。
        2. 加载知识库到内存。
        """
        validate_config()

        self._patterns_data = _load_json(PATTERNS_PATH)
        self._mechanisms_data = _load_json(MECHANISMS_PATH)
        self._alternatives_data = _load_json(ALTERNATIVES_PATH)

    # ── Knowledge Base Summaries ─────────────────────────────────

    def _get_patterns_summary(self) -> str:
        """生成行为标签库的精简摘要，用于 LLM Prompt。"""
        patterns = self._patterns_data.get("patterns", [])
        lines: list[str] = []
        for p in patterns:
            behavior = p.get("behavior", "")
            tags = p.get("tags", [])
            if behavior and tags:
                lines.append(f"- {behavior} → 标签: {', '.join(tags)}")
        return "\n".join(lines)

    def _get_mechanisms_summary(self) -> str:
        """生成心理机制库的精简摘要，用于 LLM Prompt。"""
        mechanisms = self._mechanisms_data.get("mechanisms", [])
        lines: list[str] = []
        for m in mechanisms:
            name = m.get("name", "")
            display = m.get("display_name", "")
            desc = m.get("description", "")
            if name and desc:
                lines.append(f"- {name} ({display}): {desc}")
        return "\n".join(lines)

    # ── LLM Analyze ──────────────────────────────────────────────

    async def _llm_analyze(
        self, behavior_description: str, context: Optional[str]
    ) -> dict:
        """调用 LLM 直接分析行为，返回标签、机制、替代解释。

        Args:
            behavior_description: 用户输入的行为描述。
            context: 环境上下文信息。

        Returns:
            包含 tags、mechanisms、alternative_explanations、confidence、
            universality_rating 的字典。
        """
        import logging

        logger = logging.getLogger("behavior_analyzer")

        # 使用 DeepSeek API（OpenAI 兼容接口）
        api_key = os.getenv("DEEPSEEK_API_KEY", "")
        base_url = "https://api.deepseek.com"
        model = "deepseek-chat"

        if not api_key:
            logger.warning(
                "未检测到可用的 DEEPSEEK_API_KEY，无法执行 LLM 分析"
                "→ 将返回空结果"
                "→ 建议：设置环境变量 DEEPSEEK_API_KEY"
            )
            return {
                "tags": [],
                "mechanisms": [],
                "alternative_explanations": [],
                "confidence": 0.0,
                "universality_rating": "低",
            }

        patterns_summary = self._get_patterns_summary()
        mechanisms_summary = self._get_mechanisms_summary()

        prompt = f"""你是一个行为心理分析师。根据以下行为描述，识别可能的行为标签、心理机制和替代解释。

## 行为描述
{behavior_description}

## 环境上下文
{context or "无"}

## 可用行为标签
{patterns_summary}

## 可用心理机制
{mechanisms_summary}

## 输出要求
严格按以下 JSON 格式输出，不要输出其他内容：
{{
  "tags": ["标签1", "标签2"],
  "mechanisms": [
    {{"name": "机制名", "explanation": "为什么这个机制可能适用"}}
  ],
  "alternative_explanations": [
    {{"perspective": "替代视角", "reasoning": "推理依据"}}
  ],
  "confidence": 0.0,
  "universality_rating": "高"
}}
"""

        client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        try:
            response = await client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
                temperature=0.3,
                max_tokens=1200,
            )
            content = response.choices[0].message.content or "{}"
            result = json.loads(content)

            # 规范化输出字段
            return {
                "tags": result.get("tags", []),
                "mechanisms": result.get("mechanisms", []),
                "alternative_explanations": result.get("alternative_explanations", []),
                "confidence": float(result.get("confidence", 0.0)),
                "universality_rating": result.get("universality_rating", "低"),
            }
        except Exception as e:
            logger.warning(
                f"LLM 分析调用失败（{type(e).__name__}）"
                f"→ 将返回空结果"
                f"→ 建议：检查网络连接、API Key 余额与模型可用性后重试"
            )
            return {
                "tags": [],
                "mechanisms": [],
                "alternative_explanations": [],
                "confidence": 0.0,
                "universality_rating": "低",
            }

    # ── Main Analyze ─────────────────────────────────────────────

    async def analyze(self, request: AnalysisRequest) -> AnalysisResponse:
        """对给定的行为描述请求执行心理分析。

        基于 LLM 直接推理的工作流：
        1. 边界检查：若输入涉及临床诊断/法律判定/危机情况，直接拦截。
        2. 调用 LLM 直接分析行为描述，获取标签、机制、替代解释。
        3. 组装 AnalysisResponse。
        4. 若 subject_id 不为空，更新用户画像。
        5. 返回结果（含模式摘要）。

        Args:
            request: 标准化的分析请求。

        Returns:
            标准化的分析响应。
        """
        description = request.behavior_description
        degradation_flags: list[str] = []

        # 1. 边界拦截检查
        if _check_boundary_violation(description):
            return AnalysisResponse(
                tags=[],
                psychological_mechanisms=[],
                alternative_explanations=[
                    _AlternativeExplanation(
                        perspective="边界限制",
                        reasoning="该请求涉及临床诊断/法律判定/危机情况，本工具不提供此类分析。",
                    )
                ],
                confidence=0.0,
                universality_rating="低",
                disclaimer="本工具仅用于行为模式推测，不提供临床诊断、法律意见或危机干预。若您或他人处于危机中，请寻求专业帮助。",
                blocked=True,
                degradation_flags=[],
            )

        # 2. LLM 直接分析
        llm_result = await self._llm_analyze(description, request.context)

        if not llm_result.get("tags"):
            degradation_flags.append("llm_no_tags")
        if not llm_result.get("mechanisms"):
            degradation_flags.append("llm_no_mechanisms")

        # 3. 组装结果
        tags = llm_result.get("tags", [])

        mechanisms: list[_PsychologicalMechanism] = []
        for m in llm_result.get("mechanisms", []):
            if isinstance(m, dict) and m.get("name"):
                mechanisms.append(
                    _PsychologicalMechanism(
                        name=m["name"],
                        explanation=m.get("explanation", ""),
                    )
                )

        alternatives: list[_AlternativeExplanation] = []
        for a in llm_result.get("alternative_explanations", []):
            if isinstance(a, dict) and a.get("perspective"):
                alternatives.append(
                    _AlternativeExplanation(
                        perspective=a["perspective"],
                        reasoning=a.get("reasoning", ""),
                    )
                )

        # 若 LLM 未返回替代解释，保底返回一条通用提示
        if not alternatives:
            alternatives.append(
                _AlternativeExplanation(
                    perspective="信息不足",
                    reasoning="当前行为描述未能匹配到具体的替代解释，建议补充更多上下文或观察更多行为样本后再分析。",
                )
            )

        confidence = llm_result.get("confidence", 0.0)
        universality = llm_result.get("universality_rating", "低")
        if universality not in ("高", "中", "低"):
            universality = "低"

        # 4. 获取历史画像上下文
        pattern_summary_str: Optional[str] = None
        if request.subject_id:
            profile = _get_or_create_profile(request.subject_id)
            existing_summary = profile.get("pattern_summary", "")
            if isinstance(existing_summary, str) and existing_summary.strip():
                pattern_summary_str = existing_summary

        # 5. 更新用户画像
        if request.subject_id:
            _get_or_create_profile(request.subject_id)
            try:
                _update_profile(
                    request.subject_id,
                    tags,
                    mechanisms,
                    confidence,
                    universality,
                    request,
                )
            except Exception:
                import logging
                logger = logging.getLogger("behavior_analyzer")
                logger.warning("画像更新失败")
                degradation_flags.append("profile_update_failed")

            # 重新读取画像以获取最新 pattern_summary
            profile = _get_or_create_profile(request.subject_id)
            existing_summary = profile.get("pattern_summary", "")
            if isinstance(existing_summary, str) and existing_summary.strip():
                pattern_summary_str = existing_summary

        return AnalysisResponse(
            tags=tags,
            psychological_mechanisms=mechanisms,
            alternative_explanations=alternatives,
            confidence=confidence,
            universality_rating=universality,
            subject_id=request.subject_id,
            llm_insights=None,
            pattern_summary=pattern_summary_str,
            blocked=False,
            degradation_flags=degradation_flags,
        )
