from src.openclaw_tool import register_tools


def test_openclaw_schema_exposes_privacy_opt_in() -> None:
    tool = register_tools()[0]
    assert tool["name"] == "analyzing-behavior"
    assert tool["parameters"]["properties"]["persist_profile"]["default"] is False
