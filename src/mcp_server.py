"""MCP stdio 适配层（JSON-RPC 2.0，换行分帧）。"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
from typing import Any, Optional

from src.analyzer import DefaultBehaviorAnalyzer
from src.config import RuntimeConfig, validate_config
from src.interfaces import BehaviorAnalyzer
from src.schemas import AnalysisRequest

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s: %(message)s", stream=sys.stderr)
logger = logging.getLogger("mcp_server")

SERVER_NAME = "behavior-psychology-mcp-server"
SERVER_VERSION = "2.1.0"
SUPPORTED_PROTOCOLS = ("2025-06-18", "2025-03-26", "2024-11-05")
MAX_MESSAGE_BYTES = 1_048_576

TOOL_DEFINITION = {
    "name": "analyzing-behavior",
    "description": (
        "根据有限的行为描述整理多种非诊断假设。不会判断人格、疾病或真实动机；"
        "默认不保存人物画像。"
    ),
    "inputSchema": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "behavior_description": {"type": "string", "minLength": 2, "maxLength": 4000},
            "subject_id": {
                "type": "string",
                "minLength": 1,
                "maxLength": 128,
                "pattern": "^[A-Za-z0-9_.:-]+$",
                "description": "匿名对象 ID；仅在 persist_profile=true 时用于本机画像。",
            },
            "context": {"type": "string", "maxLength": 4000, "description": "已脱敏的情境信息。"},
            "request_id": {"type": "string", "minLength": 1, "maxLength": 128},
            "persist_profile": {
                "type": "boolean",
                "default": False,
                "description": "显式同意保存本次观察；默认 false。",
            },
        },
        "required": ["behavior_description"],
        "allOf": [
            {
                "if": {"properties": {"persist_profile": {"const": True}}, "required": ["persist_profile"]},
                "then": {"required": ["subject_id", "request_id"]},
            }
        ],
    },
}


def _make_response(request_id: Any, result: Any) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def _make_error(request_id: Any, code: int, message: str, data: Any = None) -> dict[str, Any]:
    error: dict[str, Any] = {"code": code, "message": message}
    if data is not None:
        error["data"] = data
    return {"jsonrpc": "2.0", "id": request_id, "error": error}


class BehaviorPsychologyMCPServer:
    def __init__(
        self,
        analyzer: Optional[BehaviorAnalyzer] = None,
        config: Optional[RuntimeConfig] = None,
    ) -> None:
        if analyzer is None:
            runtime_config = config or validate_config()
            analyzer = DefaultBehaviorAnalyzer(config=runtime_config)
        self._analyzer = analyzer
        self._pending: dict[str | int, asyncio.Task[None]] = {}
        self._write_lock = asyncio.Lock()

    async def run(self) -> None:
        loop = asyncio.get_running_loop()
        reader = asyncio.StreamReader(limit=MAX_MESSAGE_BYTES)
        protocol = asyncio.StreamReaderProtocol(reader)
        await loop.connect_read_pipe(lambda: protocol, sys.stdin)
        logger.info("MCP Server 已启动")

        while True:
            try:
                line = await reader.readline()
            except ValueError:
                await self._send(_make_error(None, -32600, "Message too large"))
                continue
            if not line:
                break
            if len(line) > MAX_MESSAGE_BYTES:
                await self._send(_make_error(None, -32600, "Message too large"))
                continue
            try:
                message = json.loads(line.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                await self._send(_make_error(None, -32700, "Parse error"))
                continue

            if not isinstance(message, dict):
                await self._send(_make_error(None, -32600, "Invalid Request"))
                continue
            if "id" not in message:
                await self._handle_notification(message)
                continue
            request_id = message.get("id")
            if isinstance(request_id, bool) or not isinstance(request_id, (str, int)):
                await self._send(_make_error(None, -32600, "Invalid Request"))
                continue
            if request_id in self._pending:
                await self._send(_make_error(request_id, -32600, "Duplicate request id"))
                continue
            task = asyncio.create_task(self._process_and_send(message))
            self._pending[request_id] = task

        if self._pending:
            await asyncio.gather(*self._pending.values(), return_exceptions=True)
        close = getattr(self._analyzer, "close", None)
        if close is not None:
            result = close()
            if hasattr(result, "__await__"):
                await result

    async def _process_and_send(self, message: dict[str, Any]) -> None:
        request_id = message["id"]
        try:
            response = await self._handle_request(message)
            await self._send(response)
        except asyncio.CancelledError:
            logger.info("请求已取消：id=%s", request_id)
        except Exception:
            logger.exception("请求处理失败：id=%s", request_id)
            await self._send(_make_error(request_id, -32603, "Internal error"))
        finally:
            self._pending.pop(request_id, None)

    async def _handle_notification(self, message: dict[str, Any]) -> None:
        if message.get("jsonrpc") != "2.0" or not isinstance(message.get("method"), str):
            return
        method = message["method"]
        if method == "notifications/initialized":
            logger.info("客户端初始化完成")
            return
        if method == "notifications/cancelled":
            params = message.get("params", {})
            if isinstance(params, dict):
                request_id = params.get("requestId")
                if isinstance(request_id, (str, int)) and not isinstance(request_id, bool):
                    task = self._pending.get(request_id)
                    if task is not None:
                        task.cancel()
            return
        logger.debug("忽略未知 notification：%s", method)

    async def _handle_request(self, request: dict[str, Any]) -> dict[str, Any]:
        request_id = request["id"]
        if request.get("jsonrpc") != "2.0" or not isinstance(request.get("method"), str):
            return _make_error(request_id, -32600, "Invalid Request")
        method = request["method"]
        params = request.get("params", {})
        if not isinstance(params, dict):
            return _make_error(request_id, -32602, "Invalid params")
        if method == "initialize":
            requested = params.get("protocolVersion")
            protocol_version = requested if requested in SUPPORTED_PROTOCOLS else SUPPORTED_PROTOCOLS[0]
            return _make_response(
                request_id,
                {
                    "protocolVersion": protocol_version,
                    "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
                    "capabilities": {"tools": {}},
                    "instructions": "默认不保存画像；保存前需显式设置 persist_profile=true。",
                },
            )
        if method == "ping":
            return _make_response(request_id, {})
        if method == "tools/list":
            return _make_response(request_id, {"tools": [TOOL_DEFINITION]})
        if method == "tools/call":
            return await self._handle_tools_call(request_id, params)
        return _make_error(request_id, -32601, "Method not found")

    async def _handle_tools_call(self, request_id: str | int, params: dict[str, Any]) -> dict[str, Any]:
        if params.get("name") != TOOL_DEFINITION["name"]:
            return _make_error(request_id, -32602, "Unknown tool")
        arguments = params.get("arguments", {})
        if not isinstance(arguments, dict):
            return _make_error(request_id, -32602, "Invalid params")
        try:
            analysis_request = AnalysisRequest.model_validate(arguments)
        except Exception:
            return _make_error(request_id, -32602, "Invalid params")
        try:
            response = await self._analyzer.analyze(analysis_request)
        except Exception:
            logger.exception("分析执行失败：id=%s", request_id)
            return _make_error(request_id, -32603, "Analysis failed")
        structured = response.model_dump(mode="json")
        return _make_response(
            request_id,
            {
                "content": [{"type": "text", "text": json.dumps(structured, ensure_ascii=False, indent=2)}],
                "structuredContent": structured,
                "isError": False,
            },
        )

    async def _send(self, response: dict[str, Any]) -> None:
        line = json.dumps(response, ensure_ascii=False, separators=(",", ":"))
        async with self._write_lock:
            sys.stdout.write(line + "\n")
            sys.stdout.flush()


def main() -> None:
    try:
        asyncio.run(BehaviorPsychologyMCPServer().run())
    except KeyboardInterrupt:
        logger.info("MCP Server 已退出")
    except RuntimeError as exc:
        logger.error("MCP Server 启动失败：%s", exc)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
