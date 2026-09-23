"""公共请求与响应契约。"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

from src.config import RuntimeConfig, validate_config


class AnalysisRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    behavior_description: str = Field(
        ...,
        description="用户观察到的具体行为；不要填写真实姓名、联系方式等直接标识符",
        min_length=2,
        max_length=4000,
    )
    subject_id: Optional[str] = Field(
        default=None,
        description="用户自定义的匿名对象 ID，仅在显式保存画像时使用",
        min_length=1,
        max_length=128,
        pattern=r"^[A-Za-z0-9_.:-]+$",
    )
    context: Optional[str] = Field(
        default=None,
        description="环境、时间、关系与触发事件；请先去除不必要的个人信息",
        max_length=4000,
    )
    request_id: Optional[str] = Field(
        default=None,
        description="请求追踪与画像写入幂等 ID",
        min_length=1,
        max_length=128,
    )
    persist_profile: bool = Field(
        default=False,
        description="是否明确同意把本次观察写入本机画像；默认不保存",
    )

    @model_validator(mode="after")
    def _validate_profile_consent(self) -> "AnalysisRequest":
        if self.persist_profile and not self.subject_id:
            raise ValueError("persist_profile=true 时必须提供匿名 subject_id")
        if self.persist_profile and not self.request_id:
            raise ValueError("persist_profile=true 时必须提供稳定的 request_id 以支持幂等")
        return self


class _PsychologicalMechanism(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str = Field(..., min_length=1, max_length=100, description="知识库中的非诊断机制名称")
    explanation: str = Field(..., min_length=1, max_length=800, description="该机制为何可能适用")
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="模型估计的相对把握度，不是经验概率或临床分数",
    )
    universality_rating: str = Field(..., pattern=r"^(高|中|低)$")


class _AlternativeExplanation(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    perspective: str = Field(..., min_length=1, max_length=120)
    reasoning: str = Field(..., min_length=1, max_length=800)


class AnalysisResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tags: list[str] = Field(default_factory=list, max_length=8, description="知识库白名单内的行为标签")
    psychological_mechanisms: list[_PsychologicalMechanism] = Field(default_factory=list, max_length=6)
    alternative_explanations: list[_AlternativeExplanation] = Field(default_factory=list, max_length=8)
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="模型根据有限文本估计的相对把握度；未经统计校准，不代表事实概率",
    )
    confidence_basis: str = Field(
        default="模型基于有限文本的未校准估计，不是测量结果或事实概率。",
        max_length=300,
    )
    universality_rating: str = Field(..., pattern=r"^(高|中|低)$")
    disclaimer: str = Field(
        default=(
            "本分析只提供待验证的行为假设，不构成临床诊断、法律意见"
            "或对真实动机的判断。"
            "请结合当事人的直接沟通与更多情境信息。"
        )
    )
    limitations: list[str] = Field(
        default_factory=lambda: [
            "输入来自单方、有限的行为描述",
            "置信度未经统计校准",
            "标签描述行为假设，不描述人格或疾病",
        ]
    )
    subject_id: Optional[str] = None
    pattern_summary: Optional[str] = None
    profile_persisted: bool = False
    blocked: bool = False
    safety_category: Optional[str] = None
    degradation_flags: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _require_multiple_alternatives(self) -> "AnalysisResponse":
        if not self.blocked and len(self.alternative_explanations) < 2:
            raise ValueError("非拦截结果必须提供至少两个替代解释")
        return self


__all__ = [
    "AnalysisRequest",
    "AnalysisResponse",
    "RuntimeConfig",
    "_AlternativeExplanation",
    "_PsychologicalMechanism",
    "validate_config",
]
