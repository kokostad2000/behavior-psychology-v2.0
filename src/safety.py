"""输入边界与模型输出安全规则。"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class BoundaryDecision:
    category: str
    message: str


_CRISIS_TERMS = (
    "自杀",
    "自残",
    "轻生",
    "不想活",
    "结束生命",
    "伤害自己",
    "suicide",
    "suicidal",
    "self-harm",
    "伤害他人",
    "伤害别人",
    "杀了他",
    "杀了她",
    "杀人",
    "homicide",
    "kill him",
    "kill her",
    "kill them",
)
_ABUSE_TERMS = ("虐待", "家暴", "性侵", "被打", "人身威胁", "abuse", "domestic violence")
_CLINICAL_LABELS = (
    "npd",
    "bpd",
    "ocd",
    "ptsd",
    "人格障碍",
    "抑郁症",
    "抑郁障碍",
    "焦虑症",
    "焦虑障碍",
    "双相情感障碍",
    "注意缺陷多动障碍",
    "自闭症",
    "反社会人格",
    "精神分裂",
    "adhd",
    "autism",
    "autistic",
    "bipolar disorder",
    "psychopath",
    "sociopath",
    "mental disorder",
    "personality disorder",
    "narcissistic personality disorder",
)
_DIAGNOSIS_INTENT = (
    "诊断",
    "是不是",
    "是否患有",
    "有没有病",
    "确诊",
    "diagnose",
    "does he have",
    "does she have",
)
_LEGAL_INTENT = (
    "是否违法",
    "违法吗",
    "构成犯罪",
    "犯罪吗",
    "能否起诉",
    "判刑",
    "责任认定",
    "法律责任",
    "法律定性",
    "is this illegal",
)
_NEGATED_CRISIS = re.compile(
    r"(?:没有|并无|无|否认|不再).{0,5}(?:自杀|自残|轻生|不想活|伤害自己|suicidal|self-harm)",
    re.IGNORECASE,
)
_DIRECT_IDENTIFIER_PATTERNS = (
    re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE),
    re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)"),
    re.compile(r"(?<!\d)\d{17}[\dXx](?!\d)"),
)


def check_boundary(description: str, context: Optional[str] = None) -> Optional[BoundaryDecision]:
    """检查描述与上下文；返回 ``None`` 表示可继续分析。"""

    combined = f"{description}\n{context or ''}".strip().lower()
    crisis_scan = _NEGATED_CRISIS.sub("", combined)
    if any(term in crisis_scan for term in _CRISIS_TERMS):
        return BoundaryDecision(
            category="crisis",
            message=(
                "这段内容可能涉及立即安全风险，本工具不会推测当事人的心理动机。"
                "如果有人可能马上伤害自己或他人，请立即联系当地急救/警方或危机热线，"
                "并联系可信赖的人陪伴；中国大陆可拨打 120 或 110。"
            ),
        )
    if any(term in combined for term in _ABUSE_TERMS):
        return BoundaryDecision(
            category="abuse",
            message=(
                "这段内容可能涉及虐待或人身安全。本工具不会解释施害者动机。"
                "请优先确保安全、保存必要证据，并联系当地警方、医疗机构"
                "或可信赖的支持人员。"
            ),
        )
    if any(label in combined for label in _CLINICAL_LABELS) and any(
        intent in combined for intent in _DIAGNOSIS_INTENT
    ):
        return BoundaryDecision(
            category="clinical_diagnosis",
            message=(
                "本工具不能诊断精神或人格障碍；可以改为讨论可观察到的具体行为"
                "及多种情境解释。"
            ),
        )
    if any(intent in combined for intent in _LEGAL_INTENT):
        return BoundaryDecision(
            category="legal_determination",
            message=(
                "本工具不能作出违法、犯罪或责任认定；"
                "请向具备当地执业资格的法律专业人士咨询。"
            ),
        )
    if any(pattern.search(combined) for pattern in _DIRECT_IDENTIFIER_PATTERNS):
        return BoundaryDecision(
            category="personal_data",
            message=(
                "输入中可能包含邮箱、手机号码或身份证号。"
                "请删除直接身份标识，只保留分析所需的匿名情境后再试。"
            ),
        )
    return None


def contains_prohibited_clinical_label(text: str) -> bool:
    lowered = text.lower()
    return any(label in lowered for label in _CLINICAL_LABELS)
