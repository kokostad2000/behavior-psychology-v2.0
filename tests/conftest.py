"""pytest 全局 fixtures。"""

import os
from unittest.mock import MagicMock, patch

import pytest

from src.analyzer import DefaultBehaviorAnalyzer


@pytest.fixture
def mock_api_key(monkeypatch):
    """设置 mock API Key，避免测试时依赖真实环境变量。"""
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-mock-key")


@pytest.fixture
def mock_openai_client():
    """Mock OpenAI 客户端，避免真实 API 调用。"""
    mock_client = MagicMock()
    mock_embedding = MagicMock()
    mock_embedding.data = [MagicMock(embedding=[0.1] * 1536)]
    mock_client.embeddings.create.return_value = mock_embedding

    mock_chat = MagicMock()
    mock_choice = MagicMock()
    mock_choice.message.content = """
    {
        "reasoning": "测试推理",
        "mechanisms": [{"name": "测试机制", "confidence": 0.8}],
        "alternative_perspectives": [{"perspective": "测试视角", "reasoning": "测试解释"}],
        "confidence": 0.8,
        "universality_rating": "中"
    }
    """
    mock_chat.choices = [mock_choice]
    mock_client.chat.completions.create.return_value = mock_chat

    return mock_client


@pytest.fixture
def analyzer(mock_api_key, mock_openai_client):
    """提供已初始化的 DefaultBehaviorAnalyzer fixture，使用 mock API Key。"""
    with patch("src.analyzer.OpenAI", return_value=mock_openai_client):
        with patch("src.analyzer._load_json", side_effect=_mock_load_json):
            with patch("src.analyzer._save_json"):
                with patch("src.analyzer._load_profiles", return_value={}):
                    with patch("src.analyzer._save_profiles"):
                        instance = DefaultBehaviorAnalyzer()
                        return instance


def _mock_load_json(path: str):
    """Mock 加载 JSON 数据文件，返回最小可用数据集。"""
    basename = os.path.basename(path)
    if basename == "behavior_patterns.json":
        return {
            "patterns": [
                {
                    "pattern_id": "P001",
                    "name": "打断他人发言",
                    "keywords": ["打断", "插话", "会议"],
                    "tags": ["支配行为", "低同理心"],
                }
            ]
        }
    elif basename == "psychological_mechanisms.json":
        return {
            "mechanisms": [
                {
                    "mechanism_id": "M001",
                    "name": "自我中心偏差",
                    "related_tags": ["支配行为", "低同理心"],
                    "description": "过度关注自身需求而忽略他人感受",
                }
            ]
        }
    elif basename == "alternative_explanations.json":
        return {
            "rules": [
                {
                    "rule_id": "R001",
                    "trigger_tags": ["支配行为"],
                    "explanations": [
                        {
                            "perspective": "情境压力",
                            "reasoning": "可能因时间紧迫而急于表达",
                        }
                    ],
                }
            ]
        }
    elif basename == "cases.json":
        return {
            "cases": [
                {
                    "case_id": "C001",
                    "behavior_description": "同事在会议中多次打断我发言",
                    "behavior_tags": ["支配行为", "低同理心"],
                    "embedding": [0.1] * 1536,
                }
            ]
        }
    return {}
