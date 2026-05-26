import pytest
from src.analyzer import _check_boundary_violation, _generate_pattern_summary

class TestBoundaryViolation:
    def test_clinical_triggers_block(self):
        assert _check_boundary_violation("帮我诊断抑郁症") is True
    def test_normal_passes(self):
        assert _check_boundary_violation("同事打断我") is False

class TestPatternSummary:
    def test_empty(self):
        summary, tags, mechs = _generate_pattern_summary({"behavior_history":[]})
        assert summary == ""
        assert tags == []
        assert mechs == []
    def test_insufficient(self):
        p = {"behavior_history":[{"tags":["a"],"mechanisms":[]},{"tags":["b"],"mechanisms":[]}]}
        summary, tags, mechs = _generate_pattern_summary(p)
        assert "未呈现明显重复规律" in summary
        assert tags == []
        assert mechs == []
    def test_repeated(self):
        p = {"behavior_history":[{"tags":["x"],"mechanisms":["m"]},{"tags":["x"],"mechanisms":["m"]},{"tags":["x"],"mechanisms":["m"]}]}
        summary, tags, mechs = _generate_pattern_summary(p)
        assert "并非稳定人格特质" in summary
        assert "x" in tags
        assert "m" in mechs
