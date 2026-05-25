"""
核心分析器模块：实现 DefaultBehaviorAnalyzer，串联完整的心理分析工作流。

工作流：输入解析 → 知识库检索 → 机制匹配 → 结果组装 → 画像更新
"""

import json
import math
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from src.interfaces import BehaviorAnalyzer
from src.schemas import (
    AnalysisRequest,
    AnalysisResponse,
    _AlternativeExplanation,
    _LLMInsight,
    _PsychologicalMechanism,
    validate_config,
)

# ── Paths ─────────────────────────────────────────────────────────

SKILL_DIR = Path(__file__).parent.parent
KB_DIR = SKILL_DIR / "knowledge_base"
CASES_PATH = KB_DIR / "cases.json"
PATTERNS_PATH = KB_DIR / "behavior_patterns.json"
MECHANISMS_PATH = KB_DIR / "psychological_mechanisms.json"
ALTERNATIVES_PATH = KB_DIR / "alternative_explanations.json"
PROFILES_PATH = KB_DIR / "user_profiles.json"

# ── Embedding & Similarity (复用 rag_retriever 逻辑) ──────────────


def _get_openai_api_key() -> str:
    """从环境变量或 OpenClaw 配置文件中获取 OpenAI API Key。"""
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


async def _get_embedding(text: str, model: str = "text-embedding-3-small") -> List[float]:
    """通过 OpenAI API 异步生成文本的 embedding 向量。

    Args:
        text: 待编码的文本。
        model: 使用的 embedding 模型名称。

    Returns:
        浮点数列表，表示文本的向量嵌入。
        若因网络问题调用失败，降级为空向量并记录中文警告日志。

    Raises:
        RuntimeError: 当 API Key 不可用时抛出。
    """
    import logging

    logger = logging.getLogger("behavior_analyzer")

    api_key = _get_openai_api_key()
    if not api_key:
        raise RuntimeError(
            "未检测到可用的 OpenAI API Key。"
            "请至少设置以下一项："
            "1) 环境变量 OPENAI_API_KEY；"
            "2) 可读的配置文件 ~/.openclaw/openclaw.json。"
        )

    try:
        from openai import AsyncOpenAI
    except ImportError as e:
        logger.warning(
            "[降级] openai SDK 未安装，无法生成 embedding "
            f"→ 将跳过语义检索，仅依赖关键词匹配（分析精度会降低）"
            f"→ 建议：运行 `pip install openai` 后重新执行分析"
        )
        return []

    client = AsyncOpenAI(api_key=api_key)
    try:
        response = await client.embeddings.create(model=model, input=text)
        return response.data[0].embedding
    except Exception as e:
        logger.warning(
            "[降级] Embedding API 调用失败（网络或服务端问题）"
            f"→ 将跳过语义检索，仅依赖关键词匹配（分析精度会降低）"
            f"→ 建议：检查网络连接与 API Key 有效性后重试"
        )
        return []


def _cosine_similarity(a: List[float], b: List[float]) -> float:
    """计算两个向量之间的余弦相似度。

    Args:
        a: 第一个向量。
        b: 第二个向量。

    Returns:
        余弦相似度值，范围 [-1.0, 1.0]；若任一向量为零向量则返回 0.0。
    """
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


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


# ── Matching Logic ───────────────────────────────────────────────


def _match_behavior_tags(description: str, patterns: List[Dict[str, Any]]) -> List[str]:
    """基于关键词匹配从行为模式库中提取行为标签。

    同时考虑 behavior 字段和 context_hints 字段中的关键词，
    在描述文本中进行子串匹配。

    Args:
        description: 用户输入的行为描述。
        patterns: 行为模式列表。

    Returns:
        去重后的行为标签列表。
    """
    tags: set = set()
    desc_lower = description.lower()

    for pattern in patterns:
        behavior_text = pattern.get("behavior", "").lower()
        hints = [h.lower() for h in pattern.get("context_hints", [])]

        matched = False
        if behavior_text and behavior_text in desc_lower:
            matched = True
        for hint in hints:
            if hint and hint in desc_lower:
                matched = True
                break

        if matched:
            for tag in pattern.get("tags", []):
                tags.add(tag)

    return list(tags)


def _find_mechanisms(
    tags: List[str], mechanisms_data: List[Dict[str, Any]]
) -> List[_PsychologicalMechanism]:
    """根据行为标签查找对应的心理机制。

    遍历心理机制库，若机制的 name 出现在标签列表中，则纳入结果。

    Args:
        tags: 已匹配的行为标签。
        mechanisms_data: 心理机制库数据。

    Returns:
        匹配到的心理机制列表。
    """
    results: List[_PsychologicalMechanism] = []
    tag_set = set(tags)

    for mech in mechanisms_data:
        name = mech.get("name", "")
        if name in tag_set:
            results.append(
                _PsychologicalMechanism(
                    name=name,
                    explanation=mech.get("description", ""),
                )
            )

    return results


def _find_alternative_explanations(
    tags: List[str],
    rules: List[Dict[str, Any]],
    query_text: str = "",
    query_context: Optional[str] = None,
) -> List[_AlternativeExplanation]:
    """根据行为标签和场景上下文查找替代解释。

    采用双层过滤策略：
    1. 标签层：规则的 behavior_tags 与已匹配标签必须有至少 1 个交集。
    2. 场景层：若规则定义了 context_keywords（非空），则输入文本
       （behavior_description + context）必须包含至少一个关键词；
       若 context_keywords 为空数组，则跳过此层过滤（保留通用规则）。

    两层过滤均通过后，该规则的替代解释才被纳入结果。
    若最终无任何匹配，返回一条通用提示条目。

    Args:
        tags: 已匹配的行为标签。
        rules: 替代解释规则列表。
        query_text: 用户输入的行为描述文本，用于场景关键词匹配。
        query_context: 用户输入的环境上下文，用于场景关键词匹配。

    Returns:
        替代解释列表，去重后返回；若无匹配则返回通用条目。
    """
    results: List[_AlternativeExplanation] = []
    seen_perspectives: set = set()
    tag_set = set(tags)

    full_text = (query_text or "").lower()
    if query_context:
        full_text += " " + query_context.lower()

    for rule in rules:
        # 第一层：标签交集过滤
        rule_tags = set(rule.get("behavior_tags", []))
        if not (tag_set & rule_tags):
            continue

        # 第二层：场景上下文关键词过滤
        context_keywords = rule.get("context_keywords", [])
        if context_keywords:
            keywords_lower = [kw.lower() for kw in context_keywords]
            if not any(kw in full_text for kw in keywords_lower):
                continue

        for alt in rule.get("alternatives", []):
            perspective = alt.get("explanation", "")
            if perspective and perspective not in seen_perspectives:
                seen_perspectives.add(perspective)
                results.append(
                    _AlternativeExplanation(
                        perspective=perspective,
                        reasoning=f"适用场景: {', '.join(alt.get('context', []))}",
                    )
                )

    if not results:
        results.append(
            _AlternativeExplanation(
                perspective="信息不足",
                reasoning="当前行为描述未能匹配到具体的替代解释，建议补充更多上下文或观察更多行为样本后再分析。",
            )
        )

    return results


def _calculate_confidence(
    similar_cases: List[Tuple[Dict[str, Any], float]],
    matched_tags: List[str],
    mechanisms: List[_PsychologicalMechanism],
) -> Tuple[float, str]:
    """基于匹配质量计算置信度和普适性评级。

    综合以下因素：
    - 相似案例的最高相似度得分
    - 匹配到的行为标签数量
    - 识别出的心理机制数量

    Args:
        similar_cases: (案例, 相似度得分) 列表。
        matched_tags: 匹配到的行为标签。
        mechanisms: 识别出的心理机制。

    Returns:
        (confidence, universality_rating) 元组。
    """
    base_confidence = 0.0

    if similar_cases:
        top_score = similar_cases[0][1]
        base_confidence = min(top_score * 1.2, 0.6)

    tag_boost = min(len(matched_tags) * 0.08, 0.2)
    mech_boost = min(len(mechanisms) * 0.1, 0.2)

    confidence = base_confidence + tag_boost + mech_boost
    confidence = max(0.0, min(1.0, confidence))

    if confidence < 0.5:
        universality = "低"
    elif confidence < 0.75:
        universality = "中"
    else:
        universality = "高"

    return confidence, universality


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


def _generate_pattern_summary(profile: Dict[str, Any]) -> str:
    """根据 behavior_history 自动生成行为模式摘要文本。

    统计规则：
    1. 取最近 5 条历史记录（不足则取全部）。
    2. 统计出现频次 >= 2 的重复标签和重复机制。
    3. 若重复项 >= 2 个，生成结构化摘要。
    4. 若重复项不足 2 个，返回观察建议文本。

    Args:
        profile: 用户画像字典，包含 behavior_history 列表。

    Returns:
        生成的摘要字符串。
    """
    from collections import Counter

    history = profile.get("behavior_history", [])
    if not history:
        return ""

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
        return summary
    else:
        return "该对象近期行为模式未呈现明显重复规律，建议继续观察积累更多数据。"


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
            profile["pattern_summary"] = _generate_pattern_summary(profile)

    profiles[subject_id] = profile
    _save_profiles(data)


# ── DefaultBehaviorAnalyzer ──────────────────────────────────────


class DefaultBehaviorAnalyzer(BehaviorAnalyzer):
    """默认行为心理分析器实现。

    串联完整工作流：输入解析 → 知识库检索 → 机制匹配 → 结果组装 → 画像更新。
    """

    def __init__(self) -> None:
        """初始化分析器。

        执行以下步骤：
        1. 调用 validate_config() 校验配置（API Key 等）。
        2. 加载 4 个 JSON 知识库到内存。
        """
        validate_config()

        self._cases_data = _load_json(CASES_PATH)
        self._patterns_data = _load_json(PATTERNS_PATH)
        self._mechanisms_data = _load_json(MECHANISMS_PATH)
        self._alternatives_data = _load_json(ALTERNATIVES_PATH)

    async def analyze(self, request: AnalysisRequest) -> AnalysisResponse:
        """对给定的行为描述请求执行心理分析。

        完整工作流：
        1. 边界检查：若输入涉及临床诊断/法律判定/危机情况，直接拦截。
        2. 将 behavior_description 转为向量，检索 cases.json 中的相似案例。
        3. 用关键词匹配 behavior_patterns.json，提取 behavior tags。
        4. 根据 tags 查找 psychological_mechanisms.json，获取机制列表。
        5. 查找 alternative_explanations.json，获取替代解释。
        6. 基于匹配质量计算 confidence 和 universality_rating。
        7. 若 subject_id 不为空，更新用户画像。
        8. 组装并返回 AnalysisResponse（含降级标记与模式摘要）。

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

        # 2. 语义检索相似案例
        similar_cases = await self._search_similar_cases(description)
        if not similar_cases or all(score == 0.0 for _, score in similar_cases):
            degradation_flags.append("embedding_degraded")

        # 3. 关键词匹配行为标签
        matched_tags = _match_behavior_tags(
            description, self._patterns_data.get("patterns", [])
        )
        if not matched_tags:
            degradation_flags.append("keyword_only")

        if similar_cases:
            case_tags = similar_cases[0][0].get("behavior_tags", [])
            for tag in case_tags:
                if tag not in matched_tags:
                    matched_tags.append(tag)

        # 4. 查找心理机制
        mechanisms = _find_mechanisms(
            matched_tags, self._mechanisms_data.get("mechanisms", [])
        )
        if not mechanisms:
            degradation_flags.append("mechanism_not_found")

        # 5. 查找替代解释
        alternatives = _find_alternative_explanations(
            matched_tags,
            self._alternatives_data.get("rules", []),
            query_text=description,
            query_context=request.context,
        )

        # 6. 计算置信度与普适性评级
        confidence, universality = _calculate_confidence(
            similar_cases, matched_tags, mechanisms
        )

        # 7. 获取历史画像上下文（用于 LLM 增强）
        history_context = ""
        pattern_summary_str: Optional[str] = None
        if request.subject_id:
            profile = _get_or_create_profile(request.subject_id)
            existing_summary = profile.get("pattern_summary", "")
            if isinstance(existing_summary, str) and existing_summary.strip():
                history_context = existing_summary
                pattern_summary_str = existing_summary
            elif profile.get("behavior_history"):
                recent_tags: set = set()
                recent_mechs: set = set()
                for entry in profile["behavior_history"][-3:]:
                    recent_tags.update(entry.get("tags", []))
                    recent_mechs.update(entry.get("mechanisms", []))
                if recent_tags or recent_mechs:
                    parts: list[str] = []
                    if recent_tags:
                        parts.append("近期行为标签：" + ", ".join(recent_tags))
                    if recent_mechs:
                        parts.append("近期心理机制：" + ", ".join(recent_mechs))
                    history_context = "；".join(parts)

        # 8. LLM 深度分析（低置信度或机制缺失时触发）
        llm_insights = None
        if confidence < 0.5 or not mechanisms:
            llm_insights = await self._llm_deep_analysis(
                behavior_description=description,
                context=request.context,
                matched_tags=matched_tags,
                history_context=history_context,
            )
            if llm_insights is None:
                degradation_flags.append("llm_skipped")

        # 9. 更新用户画像
        if request.subject_id:
            _get_or_create_profile(request.subject_id)
            try:
                _update_profile(
                    request.subject_id,
                    matched_tags,
                    mechanisms,
                    confidence,
                    universality,
                    request,
                )
            except Exception:
                import logging
                logger = logging.getLogger("behavior_analyzer")
                logger.warning("[降级] 画像更新失败")
                degradation_flags.append("profile_update_failed")

            # 重新读取画像以获取最新 pattern_summary
            profile = _get_or_create_profile(request.subject_id)
            existing_summary = profile.get("pattern_summary", "")
            if isinstance(existing_summary, str) and existing_summary.strip():
                pattern_summary_str = existing_summary

        return AnalysisResponse(
            tags=matched_tags,
            psychological_mechanisms=mechanisms,
            alternative_explanations=alternatives,
            confidence=confidence,
            universality_rating=universality,
            subject_id=request.subject_id,
            llm_insights=llm_insights,
            pattern_summary=pattern_summary_str,
            blocked=False,
            degradation_flags=degradation_flags,
        )

    async def _llm_deep_analysis(
        self,
        behavior_description: str,
        context: Optional[str],
        matched_tags: List[str],
        history_context: str = "",
    ) -> Optional[_LLMInsight]:
        """LLM 语义增强深度分析。

        当置信度低于 0.5 或心理机制为空时自动触发，将行为描述、上下文和
        已匹配标签作为 prompt 发送给 LLM，获取结构化的深度分析结果。

        若存在历史画像数据，history_context 会被注入 prompt，让 LLM 结合
        长期行为模式给出更深入的洞察。

        LLM 调用失败时不影响基础流程，仅记录日志并跳过增强。

        Args:
            behavior_description: 用户输入的行为描述。
            context: 环境上下文信息。
            matched_tags: 已匹配的行为标签。
            history_context: 历史模式摘要文本，可选。

        Returns:
            _LLMInsight 实例或 None（调用失败时）。
        """
        import logging

        logger = logging.getLogger("behavior_analyzer")

        api_key = _get_openai_api_key()
        if not api_key:
            logger.warning(
                "[降级] 未检测到可用的 OpenAI API Key，无法执行 LLM 深度分析"
                "→ 将返回知识库基础分析结果（置信度可能较低、缺少语义增强）"
                "→ 建议：设置环境变量 OPENAI_API_KEY 或在 ~/.openclaw/openclaw.json 中配置 apiKey"
            )
            return None

        try:
            from openai import AsyncOpenAI
        except ImportError as e:
            logger.warning(
                "[降级] openai SDK 未安装，无法执行 LLM 深度分析"
                "→ 将返回知识库基础分析结果（置信度可能较低、缺少语义增强）"
                "→ 建议：运行 `pip install openai` 后重新执行分析"
            )
            return None

        prompt = self._build_llm_prompt(behavior_description, context, matched_tags, history_context)

        client = AsyncOpenAI(api_key=api_key)
        try:
            response = await client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "你是一位专业的心理学分析助手。"
                            "请根据用户提供的行为描述，从心理学角度进行深度分析。"
                            "你必须以 JSON 格式返回结果，不要包含任何其他文本。"
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                response_format={"type": "json_object"},
                temperature=0.3,
                max_tokens=800,
            )
            content = response.choices[0].message.content or "{}"
            result = json.loads(content)
            return _LLMInsight(
                mechanisms=result.get("mechanisms", []),
                biases_or_factors=result.get("biases_or_factors", []),
                observation_suggestions=result.get("observation_suggestions", []),
            )
        except Exception as e:
            logger.warning(
                f"[降级] LLM 深度分析调用失败（{type(e).__name__}）"
                f"→ 将返回知识库基础分析结果（置信度可能较低、缺少语义增强）"
                f"→ 建议：检查网络连接、API Key 余额与模型可用性后重试"
            )
            return None

    def _build_llm_prompt(
        self,
        behavior_description: str,
        context: Optional[str],
        matched_tags: List[str],
        history_context: str = "",
    ) -> str:
        """构建 LLM 深度分析的 prompt。

        Args:
            behavior_description: 行为描述。
            context: 环境上下文。
            matched_tags: 已匹配标签。
            history_context: 历史模式摘要文本，可选。

        Returns:
            格式化后的 prompt 字符串。
        """
        lines = [
            "请对以下行为进行心理学深度分析：",
            "",
            f"行为描述：{behavior_description}",
        ]
        if context:
            lines.append(f"上下文：{context}")
        if matched_tags:
            lines.append(f"已匹配的行为标签：{', '.join(matched_tags)}")
        if history_context:
            lines.append(f"历史行为模式：{history_context}")
        lines.extend([
            "",
            "请返回以下 JSON 格式的分析结果（仅返回 JSON，不要其他内容）：",
            "{",
            '  "mechanisms": ["机制1", "机制2"],',
            '  "biases_or_factors": ["偏差/因素1", "偏差/因素2"],',
            '  "observation_suggestions": ["建议1", "建议2"]',
            "}",
        ])
        return "\n".join(lines)

    async def _search_similar_cases(
        self, query_text: str, top_k: int = 3
    ) -> List[Tuple[Dict[str, Any], float]]:
        """检索与查询文本语义相似的案例。

        先为查询文本生成 embedding，再与案例库中的 embedding 计算余弦相似度，
        返回得分最高的 top_k 个案例。

        Args:
            query_text: 查询文本（行为描述）。
            top_k: 返回的最大案例数量。
                设计依据：返回 top-3 案例在覆盖度与信噪比之间取得平衡。
                少于 3 可能遗漏相关案例，多于 3 可能引入噪声降低匹配置信度。

        Returns:
            (案例字典, 相似度得分) 列表，按得分降序排列。
        """
        cases = self._cases_data.get("cases", [])
        if not cases:
            return []

        try:
            query_emb = await _get_embedding(query_text)
        except RuntimeError:
            query_emb = []

        results: List[Tuple[Dict[str, Any], float]] = []
        for case in cases:
            case_emb = case.get("embedding", [])
            if query_emb and case_emb:
                score = _cosine_similarity(query_emb, case_emb)
            else:
                score = 0.0
            results.append((case, score))

        results.sort(key=lambda x: x[1], reverse=True)
        return results[:top_k]
