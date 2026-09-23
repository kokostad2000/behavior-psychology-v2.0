import pytest
from pydantic import ValidationError

from src.schemas import AnalysisRequest, AnalysisResponse


def test_profile_write_requires_subject_and_request_ids() -> None:
    with pytest.raises(ValidationError):
        AnalysisRequest(behavior_description="同事打断我", persist_profile=True)


def test_non_blocked_response_requires_two_alternatives() -> None:
    with pytest.raises(ValidationError, match="至少两个"):
        AnalysisResponse(
            confidence=0,
            universality_rating="低",
            alternative_explanations=[],
        )
