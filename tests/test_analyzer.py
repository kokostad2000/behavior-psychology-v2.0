from __future__ import annotations

import asyncio
import json

from src.analyzer import _check_boundary_violation, _generate_pattern_summary
from src.schemas import AnalysisRequest

VALID_RESULT = json.dumps(
    {
        "tags": ["conversation_interruption", "turn_taking_overlap"],
        "mechanisms": [
            {
                "name": "role_or_norm_expectation",
                "explanation": "主持职责或团队规范可能改变发言顺序",
                "confidence": 0.55,
            },
            {
                "name": "situational_stress",
                "explanation": "时间压力可能使发言节奏加快",
                "confidence": 0.45,
            },
        ],
        "alternative_explanations": [
            {"perspective": "时间压力", "reasoning": "会议时间不足可能使发言更急促"},
            {"perspective": "沟通习惯", "reasoning": "某些团队允许更频繁的交叉发言"},
        ],
        "confidence": 0.55,
        "universality_rating": "中",
    },
    ensure_ascii=False,
)


def test_boundary_checks_context_and_negation() -> None:
    assert _check_boundary_violation("他最近不回复我", "请诊断是不是抑郁症") is True
    assert _check_boundary_violation("他明确说自己没有自杀想法") is False
    assert _check_boundary_violation("同事打断我") is False


def test_pattern_summary_refreshes_from_recent_history() -> None:
    profile = {
        "behavior_history": [
            {"tags": ["old"], "mechanisms": ["old_mech"]},
            {"tags": ["new"], "mechanisms": ["new_mech"]},
            {"tags": ["new"], "mechanisms": ["new_mech"]},
        ]
    }
    summary, tags, mechanisms = _generate_pattern_summary(profile)
    assert "new" in summary
    assert tags == ["new"]
    assert mechanisms == ["new_mech"]


def test_valid_analysis_uses_system_instruction_and_whitelist(analyzer_factory) -> None:
    analyzer, client, _ = analyzer_factory(VALID_RESULT)
    request = AnalysisRequest(
        behavior_description="同事在会议中多次打断我的发言",
        context="项目周会",
    )
    response = asyncio.run(analyzer.analyze(request))
    assert response.blocked is False
    assert response.tags == ["conversation_interruption", "turn_taking_overlap"]
    assert len(response.alternative_explanations) >= 2
    assert client.completions.calls[0]["messages"][0]["role"] == "system"
    assert "同事在会议" not in client.completions.calls[0]["messages"][0]["content"]


def test_unknown_and_clinical_outputs_are_filtered(analyzer_factory) -> None:
    unsafe = json.dumps(
        {
            "tags": ["NPD", "conversation_interruption"],
            "mechanisms": [
                {
                    "name": "situational_stress",
                    "explanation": "他有人格障碍",
                    "confidence": 0.99,
                },
                {"name": "invented", "explanation": "虚构", "confidence": 0.9},
            ],
            "alternative_explanations": [],
            "confidence": 0.99,
            "universality_rating": "高",
        },
        ensure_ascii=False,
    )
    analyzer, _, _ = analyzer_factory(unsafe)
    response = asyncio.run(analyzer.analyze(AnalysisRequest(behavior_description="他经常打断我")))
    assert response.tags == ["conversation_interruption"]
    assert response.psychological_mechanisms == []
    assert len(response.alternative_explanations) >= 2
    assert "clinical_output_filtered" in response.degradation_flags


def test_crisis_is_blocked_without_model_call(analyzer_factory) -> None:
    analyzer, client, _ = analyzer_factory(VALID_RESULT)
    response = asyncio.run(analyzer.analyze(AnalysisRequest(behavior_description="我现在想自残")))
    assert response.blocked is True
    assert response.safety_category == "crisis"
    assert client.completions.calls == []


def test_direct_identifier_is_blocked_before_model_call(analyzer_factory) -> None:
    analyzer, client, _ = analyzer_factory(VALID_RESULT)
    response = asyncio.run(
        analyzer.analyze(AnalysisRequest(behavior_description="联系人 13800138000 最近不回复我"))
    )
    assert response.blocked is True
    assert response.safety_category == "personal_data"
    assert client.completions.calls == []


def test_api_failure_is_explicit_and_not_persisted(analyzer_factory) -> None:
    analyzer, _, store = analyzer_factory(error=TimeoutError("timeout"))
    response = asyncio.run(
        analyzer.analyze(
            AnalysisRequest(
                behavior_description="同事打断我",
                subject_id="colleague_a",
                request_id="req-1",
                persist_profile=True,
            )
        )
    )
    assert response.confidence == 0
    assert "llm_api_error" in response.degradation_flags
    assert store.get("colleague_a") is None


def test_profile_is_opt_in_and_idempotent(analyzer_factory) -> None:
    analyzer, _, store = analyzer_factory(VALID_RESULT)
    base = AnalysisRequest(behavior_description="同事打断我", subject_id="colleague_a")
    asyncio.run(analyzer.analyze(base))
    assert store.get("colleague_a") is None

    persisted = AnalysisRequest(
        behavior_description="同事打断我",
        subject_id="colleague_a",
        request_id="req-stable",
        persist_profile=True,
    )
    first = asyncio.run(analyzer.analyze(persisted))
    second = asyncio.run(analyzer.analyze(persisted))
    profile = store.get("colleague_a")
    assert first.profile_persisted is True
    assert second.profile_persisted is False
    assert "duplicate_request_ignored" in second.degradation_flags
    assert profile is not None
    assert len(profile["behavior_history"]) == 1
