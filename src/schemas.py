import json
import os
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class AnalysisRequest(BaseModel):
    behavior_description: str = Field(
        ...,
        description="用户描述的行为文本，包含观察到的具体行为、言语或社交互动场景",
        min_length=1,
    )
    subject_id: Optional[str] = Field(
        default=None,
        description="被分析对象的历史人物 ID，用于长期追踪与画像关联（例如 colleague_A、friend_X）",
    )
    context: Optional[str] = Field(
        default=None,
        description="环境上下文信息，包括时间、地点、触发事件、在场人员、关系背景等",
    )
    request_id: Optional[str] = Field(
        default=None,
        description="请求追踪 ID，用于链路追踪、日志关联与幂等性控制",
    )


class _PsychologicalMechanism(BaseModel):
    name: str = Field(..., description="心理机制名称，例如 boundary_setting、emotional_regulation")
    explanation: str = Field(..., description="对该机制在当前情境下适用性的中文解释")


class _AlternativeExplanation(BaseModel):
    perspective: str = Field(..., description="替代解释视角，例如 '工作压力'、'社交疲劳'")
    reasoning: str = Field(..., description="该视角的中文推理说明")


class AnalysisResponse(BaseModel):
    tags: list[str] = Field(
        default_factory=list,
        description="匹配到的行为标签列表，例如 ['avoidance', 'boundary_setting', 'emotional_overwhelm']",
    )
    psychological_mechanisms: list[_PsychologicalMechanism] = Field(
        default_factory=list,
        description="识别出的心理机制列表，每项包含机制名称与解释",
    )
    alternative_explanations: list[_AlternativeExplanation] = Field(
        default_factory=list,
        description="替代解释列表，每项包含视角与推理，必须提供至少 2-3 条",
    )
    confidence: float = Field(
        ...,
        description="整体分析置信度，取值范围 0.0-1.0；若低于 0.5 应明确提示信息不足",
        ge=0.0,
        le=1.0,
    )
    universality_rating: str = Field(
        ...,
        description="普适性评级：'高'表示普遍人类心理机制，'中'表示情境依赖，'低'表示个体差异大",
        pattern=r"^(高|中|低)$",
    )
    disclaimer: str = Field(
        default="本分析仅基于有限信息的推测，不构成临床诊断。只有当事人自己知道其真实动机与原因。",
        description="固定的免责声明文本，每次输出必须包含",
    )
    subject_id: Optional[str] = Field(
        default=None,
        description="回传的分析对象 ID，与请求中的 subject_id 保持一致，便于调用端关联",
    )
    pattern_summary: Optional[str] = Field(
        default=None,
        description="当 subject_id 历史记录 >= 3 条时，返回该对象的行为模式摘要",
    )
    blocked: bool = Field(
        default=False,
        description="是否因边界限制而未执行分析",
    )
    degradation_flags: list[str] = Field(
        default_factory=list,
        description="降级状态标签列表，空列表表示无降级。"
                    "可选值：llm_no_tags, llm_no_mechanisms, profile_update_failed",
    )

    @field_validator("universality_rating")
    @classmethod
    def _check_universality(cls, v: str) -> str:
        if v not in ("高", "中", "低"):
            raise ValueError("universality_rating 必须是 '高'、'中' 或 '低'")
        return v


def validate_config() -> None:
    """校验运行时配置，确保 AI 接入凭证可用。

    检查以下两项之一：
    1. 环境变量 OPENAI_API_KEY
    2. 配置文件 ~/.openclaw/openclaw.json（且包含 openai.apiKey）

    若两者均不可用，抛出 RuntimeError 并提供友好的中文报错信息。
    """
    openai_key = os.getenv("OPENAI_API_KEY", "").strip()
    openclaw_config_path = os.path.expanduser("~/.openclaw/openclaw.json")
    openclaw_readable = os.path.isfile(openclaw_config_path) and os.access(openclaw_config_path, os.R_OK)

    has_valid_key = False
    if openai_key:
        has_valid_key = True
    elif openclaw_readable:
        try:
            with open(openclaw_config_path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
                if cfg.get("openai", {}).get("apiKey", "").strip():
                    has_valid_key = True
        except Exception:
            pass

    if not has_valid_key:
        raise RuntimeError(
            "配置校验失败：未检测到可用的 AI 接入凭证。\n"
            "请至少设置以下一项：\n"
            "  1) 环境变量 OPENAI_API_KEY（例如：export OPENAI_API_KEY=sk-xxx）\n"
            "  2) 可读的配置文件 ~/.openclaw/openclaw.json，内容格式：\n"
            '     {"openai": {"apiKey": "sk-xxx"}}\n'
            "两者均不可用时，系统无法继续运行。"
        )
