import pytest
from src.analyzer import _check_boundary_violation, _generate_pattern_summary

class TestBoundaryViolation:
    def test_clinical_triggers_block(self):
        assert _check_boundary_violation("帮我诊断抑郁症") is True
    def test_normal_passes(self):
        assert _check_boundary_violation("同事打断我") is False

class TestPatternSummary:
    def test_empty(self):
        assert _generate_pattern_summary({"behavior_history":[]}) == ""
    def test_insufficient(self):
        p = {"behavior_history":[{"tags":["a"],"mechanisms":[]},{"tags":["b"],"mechanisms":[]}]}
        assert "未呈现明显重复规律" in _generate_pattern_summary(p)
    def test_repeated(self):
        p = {"behavior_history":[{"tags":["x"],"mechanisms":["m"]},{"tags":["x"],"mechanisms":["m"]},{"tags":["x"],"mechanisms":["m"]}]}
        assert "并非稳定人格特质" in _generate_pattern_summary(p)
