"""
MCP Server 适配层：通过 stdio 提供 JSON-RPC 2.0 接口，
将 DefaultBehaviorAnalyzer 暴露为 MCP Tool。

传输方式：stdin/stdout（JSON-RPC 2.0 over stdio）
兼容客户端：Claude Desktop、Cursor 等支持 MCP stdio 的客户端
"""

import asyncio
import json
import logging
import sys
import uuid
from typing import Any, Dict, List, Optional

from src.analyzer import DefaultBehaviorAnalyzer
from src.schemas import AnalysisRequest, validate_config

# ── 日志配置 ──────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s: %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger("mcp_server")

# ── MCP 常量 ──────────────────────────────────────────────────────

SERVER_NAME = "behavior-psychology-mcp-server"
SERVER_VERSION = "1.0.0"

# 工具定义（复用 Function Calling JSON Schema）
TOOL_DEFINITION = {
    "name": "analyzing-behavior",
    "description": (
        "分析用户描述的行为或社交互动，识别可能的心理机制、认知模式与社会因素。"
        "提供结构化分析报告，包含替代解释、普适性评级与置信度分数。"
        "适用于'帮我分析一下...'、'为什么TA会...'、'你怎么看这件事...'等场景。"
        "明确不是诊断工具，不输出人格障碍或临床标签。"
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "behavior_description": {
                "type": "string",
                "description": "用户描述的行为文本，包含观察到的具体行为、言语或社交互动场景。必填。",
            },
            "subject_id": {
                "type": "string",
                "description": "被分析对象的历史人物 ID，用于长期追踪与画像关联（例如 colleague_A、friend_X）。可选。",
            },
            "context": {
                "type": "string",
                "description": "环境上下文信息，包括时间、地点、触发事件、在场人员、关系背景等。可选。",
            },
            "request_id": {
                "type": "string",
                "description": "请求追踪 ID，用于链路追踪、日志关联与幂等性控制。可选。",
            },
        },
        "required": ["behavior_description"],
    },
}

# ── JSON-RPC 辅助函数 ────────────────────────────────────────────


def _make_response(request_id: Any, result: Any) -> Dict[str, Any]:
    """构造 JSON-RPC 2.0 成功响应。"""
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "result": result,
    }


def _make_error(request_id: Any, code: int, message: str, data: Any = None) -> Dict[str, Any]:
    """构造 JSON-RPC 2.0 错误响应。"""
    error_obj: Dict[str, Any] = {"code": code, "message": message}
    if data is not None:
        error_obj["data"] = data
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "error": error_obj,
    }


# ── MCP Server 类 ─────────────────────────────────────────────────


class BehaviorPsychologyMCPServer:
    """行为心理分析 MCP Server 实现。

    通过 stdin/stdout 与 MCP 客户端通信，支持 initialize、tools/list、tools/call 方法。
    内部持有 DefaultBehaviorAnalyzer 单例，避免重复初始化知识库。
    """

    def __init__(self) -> None:
        """初始化 MCP Server。

        1. 调用 validate_config() 校验 API Key 等配置。
        2. 创建 DefaultBehaviorAnalyzer 实例（仅一次）。
        """
        logger.info("正在校验运行时配置...")
        validate_config()
        logger.info("配置校验通过，正在初始化分析器...")
        self._analyzer = DefaultBehaviorAnalyzer()
        logger.info("分析器初始化完成，MCP Server 就绪。")

    async def run(self) -> None:
        """启动 MCP Server，从 stdin 读取 JSON-RPC 请求并处理。"""
        logger.info("MCP Server 已启动，等待客户端连接...")
        loop = asyncio.get_event_loop()
        reader = asyncio.StreamReader()
        protocol = asyncio.StreamReaderProtocol(reader)
        await loop.connect_read_pipe(lambda: protocol, sys.stdin)

        while True:
            try:
                line = await reader.readline()
            except asyncio.CancelledError:
                logger.info("MCP Server 收到取消信号，正在退出...")
                break
            if not line:
                logger.info("stdin 已关闭，MCP Server 退出。")
                break

            raw = line.decode("utf-8").strip()
            if not raw:
                continue

            try:
                request = json.loads(raw)
            except json.JSONDecodeError as e:
                logger.warning(f"收到非法 JSON: {raw[:200]}... 错误: {e}")
                response = _make_error(None, -32700, "Parse error", str(e))
                self._send(response)
                continue

            await self._handle_request(request)

    async def _handle_request(self, request: Dict[str, Any]) -> None:
        """分发并处理单个 JSON-RPC 请求。"""
        request_id = request.get("id")
        method = request.get("method")
        params = request.get("params", {})

        logger.info(f"收到请求: method={method}, id={request_id}")

        if method == "initialize":
            response = self._handle_initialize(request_id, params)
        elif method == "tools/list":
            response = self._handle_tools_list(request_id)
        elif method == "tools/call":
            response = await self._handle_tools_call(request_id, params)
        else:
            logger.warning(f"未知方法: {method}")
            response = _make_error(request_id, -32601, f"Method not found: {method}")

        self._send(response)

    def _handle_initialize(self, request_id: Any, params: Dict[str, Any]) -> Dict[str, Any]:
        """处理 initialize 请求，返回 Server 信息。"""
        client_info = params.get("clientInfo", {})
        logger.info(
            f"客户端初始化: name={client_info.get('name', 'unknown')}, "
            f"version={client_info.get('version', 'unknown')}"
        )
        result = {
            "protocolVersion": "2024-11-05",
            "serverInfo": {
                "name": SERVER_NAME,
                "version": SERVER_VERSION,
            },
            "capabilities": {
                "tools": {},
            },
        }
        logger.info("initialize 响应已发送。")
        return _make_response(request_id, result)

    def _handle_tools_list(self, request_id: Any) -> Dict[str, Any]:
        """处理 tools/list 请求，返回可用工具列表。"""
        result = {"tools": [TOOL_DEFINITION]}
        logger.info(f"tools/list 响应: 返回 {len(result['tools'])} 个工具")
        return _make_response(request_id, result)

    async def _handle_tools_call(self, request_id: Any, params: Dict[str, Any]) -> Dict[str, Any]:
        """处理 tools/call 请求，调用分析器并返回结果。"""
        tool_name = params.get("name", "")
        arguments = params.get("arguments", {})

        if tool_name != TOOL_DEFINITION["name"]:
            logger.warning(f"请求调用了未知工具: {tool_name}")
            return _make_error(request_id, -32602, f"Unknown tool: {tool_name}")

        logger.info(f"tools/call: 调用工具 {tool_name}, arguments={json.dumps(arguments, ensure_ascii=False)[:200]}")

        try:
            req = AnalysisRequest(
                behavior_description=arguments.get("behavior_description", ""),
                subject_id=arguments.get("subject_id") or None,
                context=arguments.get("context") or None,
                request_id=arguments.get("request_id") or str(uuid.uuid4()),
            )
        except Exception as e:
            logger.error(f"参数解析失败: {e}")
            return _make_error(request_id, -32602, f"Invalid params: {e}")

        try:
            response = await self._analyzer.analyze(req)
        except Exception as e:
            logger.exception("分析器执行失败")
            return _make_error(request_id, -32603, f"分析执行失败: {e}")

        result = {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps(response.model_dump(), ensure_ascii=False, indent=2),
                }
            ]
        }
        logger.info(f"tools/call: 分析完成，返回结果（confidence={response.confidence:.2f}）")
        return _make_response(request_id, result)

    def _send(self, response: Dict[str, Any]) -> None:
        """将响应对象序列化为 JSON 并写入 stdout，追加换行符。"""
        try:
            line = json.dumps(response, ensure_ascii=False)
        except (TypeError, ValueError) as e:
            line = json.dumps(_make_error(None, -32603, f"JSON 序列化失败: {e}"), ensure_ascii=False)
        sys.stdout.write(line + "\n")
        sys.stdout.flush()


# ── 入口 ──────────────────────────────────────────────────────────


def main() -> None:
    """MCP Server 主入口。"""
    try:
        server = BehaviorPsychologyMCPServer()
    except RuntimeError as e:
        logger.error(f"Server 启动失败: {e}")
        sys.stderr.write(f"错误: {e}\n")
        sys.exit(1)

    try:
        asyncio.run(server.run())
    except KeyboardInterrupt:
        logger.info("收到键盘中断，Server 退出。")
    except Exception as e:
        logger.exception("Server 运行时异常")
        sys.stderr.write(f"运行时错误: {e}\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
