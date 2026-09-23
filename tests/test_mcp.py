from __future__ import annotations

import asyncio
from types import SimpleNamespace

from src.mcp_server import BehaviorPsychologyMCPServer


class StubAnalyzer:
    async def analyze(self, request):
        return SimpleNamespace(
            model_dump=lambda **kwargs: {
                "tags": [],
                "psychological_mechanisms": [],
                "alternative_explanations": [],
                "confidence": 0.0,
            }
        )


def test_notification_has_no_response() -> None:
    server = BehaviorPsychologyMCPServer(analyzer=StubAnalyzer())
    assert (
        asyncio.run(
            server._handle_notification(
                {"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}}
            )
        )
        is None
    )


def test_ping_and_protocol_negotiation() -> None:
    server = BehaviorPsychologyMCPServer(analyzer=StubAnalyzer())
    ping = asyncio.run(server._handle_request({"jsonrpc": "2.0", "id": 1, "method": "ping"}))
    assert ping == {"jsonrpc": "2.0", "id": 1, "result": {}}
    initialized = asyncio.run(
        server._handle_request(
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "initialize",
                "params": {"protocolVersion": "2025-06-18"},
            }
        )
    )
    assert initialized["result"]["protocolVersion"] == "2025-06-18"


def test_invalid_params_do_not_leak_exception() -> None:
    server = BehaviorPsychologyMCPServer(analyzer=StubAnalyzer())
    result = asyncio.run(
        server._handle_request(
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {"name": "analyzing-behavior", "arguments": {"behavior_description": "x"}},
            }
        )
    )
    assert result["error"]["code"] == -32602


def test_valid_tool_call_returns_structured_content() -> None:
    server = BehaviorPsychologyMCPServer(analyzer=StubAnalyzer())
    result = asyncio.run(
        server._handle_request(
            {
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {
                    "name": "analyzing-behavior",
                    "arguments": {"behavior_description": "同事打断我"},
                },
            }
        )
    )
    assert "structuredContent" in result["result"]
    assert result["result"]["isError"] is False
