# API 规范 — Behavior Psychology Analyzer

## OpenAI Function Calling JSON Schema

以下 JSON Schema 可直接用于 OpenAI `tools` / `functions` 参数定义，也可作为其他 LLM 平台 Function Calling 的参考模板。

```json
{
  "name": "analyzing-behavior",
  "description": "分析用户描述的行为或社交互动，识别可能的心理机制、认知模式与社会因素。提供结构化分析报告，包含替代解释、普适性评级与置信度分数。适用于'帮我分析一下...'、'为什么TA会...'、'你怎么看这件事...'等场景。明确不是诊断工具，不输出人格障碍或临床标签。",
  "parameters": {
    "type": "object",
    "properties": {
      "behavior_description": {
        "type": "string",
        "description": "用户描述的行为文本，包含观察到的具体行为、言语或社交互动场景。必填。"
      },
      "subject_id": {
        "type": "string",
        "description": "被分析对象的历史人物 ID，用于长期追踪与画像关联（例如 colleague_A、friend_X）。可选。"
      },
      "context": {
        "type": "string",
        "description": "环境上下文信息，包括时间、地点、触发事件、在场人员、关系背景等。可选。"
      },
      "request_id": {
        "type": "string",
        "description": "请求追踪 ID，用于链路追踪、日志关联与幂等性控制。可选。"
      }
    },
    "required": ["behavior_description"]
  }
}
```

## 返回结构 Schema

Function Calling 的返回（即 `AnalysisResponse` 的 JSON 表示）应遵循以下结构：

```json
{
  "type": "object",
  "properties": {
    "tags": {
      "type": "array",
      "items": { "type": "string" },
      "description": "匹配到的行为标签列表，例如 ['avoidance', 'boundary_setting']"
    },
    "psychological_mechanisms": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "name": { "type": "string", "description": "心理机制名称" },
          "explanation": { "type": "string", "description": "对该机制在当前情境下适用性的中文解释" }
        },
        "required": ["name", "explanation"]
      },
      "description": "识别出的心理机制列表"
    },
    "alternative_explanations": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "perspective": { "type": "string", "description": "替代解释视角" },
          "reasoning": { "type": "string", "description": "该视角的中文推理说明" }
        },
        "required": ["perspective", "reasoning"]
      },
      "description": "替代解释列表，必须提供至少 2-3 条"
    },
    "confidence": {
      "type": "number",
      "minimum": 0.0,
      "maximum": 1.0,
      "description": "整体分析置信度，0.0-1.0；低于 0.5 应明确提示信息不足"
    },
    "universality_rating": {
      "type": "string",
      "enum": ["高", "中", "低"],
      "description": "普适性评级：高=普遍人类心理机制，中=情境依赖，低=个体差异大"
    },
    "disclaimer": {
      "type": "string",
      "description": "固定的免责声明文本"
    },
    "subject_id": {
      "type": "string",
      "description": "回传的分析对象 ID，与请求中的 subject_id 保持一致"
    },
    "pattern_summary": {
      "type": "string",
      "description": "当同一对象历史记录 >= 3 条时，自动生成的行为模式摘要"
    },
    "blocked": {
      "type": "boolean",
      "description": "是否因边界限制（临床诊断/法律/危机）而未执行分析"
    },
    "degradation_flags": {
      "type": "array",
      "items": { "type": "string" },
      "description": "降级状态标签，例如 llm_no_tags, profile_update_failed"
    }
  },
  "required": ["tags", "psychological_mechanisms", "alternative_explanations", "confidence", "universality_rating", "disclaimer"]
}
```

## MCP Tool 注解

若将本 Skill 暴露为 MCP (Model Context Protocol) Server 的 Tool，应在 `tools/list` 响应中按以下格式注册：

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "tools": [
      {
        "name": "behavior_psychology_analyze",
        "description": "分析用户描述的行为或社交互动，识别可能的心理机制、认知模式与社会因素。提供结构化分析报告，包含替代解释、普适性评级与置信度分数。明确不是诊断工具，不输出人格障碍或临床标签。",
        "inputSchema": {
          "type": "object",
          "properties": {
            "behavior_description": {
              "type": "string",
              "description": "用户描述的行为文本，包含观察到的具体行为、言语或社交互动场景。必填。"
            },
            "subject_id": {
              "type": "string",
              "description": "被分析对象的历史人物 ID，用于长期追踪与画像关联。可选。"
            },
            "context": {
              "type": "string",
              "description": "环境上下文信息，包括时间、地点、触发事件、在场人员、关系背景等。可选。"
            },
            "request_id": {
              "type": "string",
              "description": "请求追踪 ID，用于链路追踪、日志关联与幂等性控制。可选。"
            }
          },
          "required": ["behavior_description"]
        }
      }
    ]
  }
}
```

### MCP 集成要点

1. **Server 实现**：实现 `BehaviorAnalyzer` 抽象基类的具体类，在 `tools/call` 处理方法中解析 `arguments` 为 `AnalysisRequest`，调用 `analyze()` 后将 `AnalysisResponse` 序列化为 JSON 返回。
2. **配置校验**：Server 启动时必须先调用 `validate_config()`，确保 `DEEPSEEK_API_KEY`、`OPENAI_API_KEY` 或 `~/.openclaw/openclaw.json` 至少一项可用，否则拒绝启动并返回明确的中文错误信息。
3. **生命周期管理**：建议将 `BehaviorAnalyzer` 实例作为 Server 的共享依赖注入，避免每次请求重复初始化知识库。
4. **错误映射**：将 `validate_config()` 抛出的 `RuntimeError` 映射为 MCP 的 `-32603` (Internal Error) 并附带中文 `message`，便于客户端排查。

---

## MCP 接入指南

本 Skill 已内置轻量级 MCP Server（`src/mcp_server.py`），通过 **stdio 传输**（JSON-RPC 2.0 over stdin/stdout）与 MCP 客户端通信，无需额外依赖。

### 启动方式

```bash
python -m src.mcp_server
```

或直接在项目根目录执行：

```bash
python src/mcp_server.py
```

### Claude Desktop 配置

在 Claude Desktop 的配置文件（`~/Library/Application Support/Claude/claude_desktop_config.json`）中添加 `mcpServers` 字段：

```json
{
  "mcpServers": {
    "behavior-psychology": {
      "command": "python",
      "args": [
        "/absolute/path/to/behavior-psychology/src/mcp_server.py"
      ],
      "env": {
        "DEEPSEEK_API_KEY": "sk-xxx"
      }
    }
  }
}
```

> **注意**：
> - `args` 中的路径必须使用**绝对路径**。
> - `env` 中设置 `DEEPSEEK_API_KEY` 是推荐做法；也可省略，改为在 `~/.openclaw/openclaw.json` 中配置 `deepseek.apiKey`。
> - 配置保存后重启 Claude Desktop，客户端会自动通过 `initialize` → `tools/list` 完成握手与工具发现。

### 支持的 MCP 方法

| 方法 | 说明 |
|------|------|
| `initialize` | 返回 Server 信息（protocolVersion、serverInfo、capabilities） |
| `tools/list` | 返回可用工具列表（当前仅 `behavior_psychology_analyze`） |
| `tools/call` | 接收工具调用请求，解析参数后调用分析器，返回 `AnalysisResponse` 的 JSON |

---

## OpenClaw 接入指南

本 Skill 已内置 OpenClaw 插件规范实现（`src/openclaw_tool.py`），提供标准化的 `register_tools()` 与 `handle_tool_call()` 接口。

### 注册方式

在 OpenClaw Agent 的插件配置中，将本模块路径加入扫描列表：

```python
# OpenClaw Agent 启动脚本示例
from src.openclaw_tool import register_tools, handle_tool_call

# 注册工具
tools = register_tools()
for tool in tools:
    agent.register_tool(tool, handler=handle_tool_call)
```

### 配置文件

OpenClaw 额外配置存放在 `~/.openclaw/openclaw.json`，格式如下：

```json
{
  "deepseek": {
    "apiKey": "sk-xxx"
  }
}
```

当前预留扩展点：未来可在该配置中覆盖默认模型、温度参数等。

### 独立测试

直接运行模块即可进行本地测试：

```bash
python -m src.openclaw_tool
```

该命令会模拟一次工具注册与调用，输出分析结果到终端。

---

## CLI 接入示例

已有的命令行入口（`src/cli.py`）支持以下用法：

### 执行行为分析

```bash
python -m src.cli analyze \
  --behavior "同事总是最后一个回复我的消息" \
  --subject colleague_A \
  --context "工作群聊"
```

参数说明：

| 参数 | 必填 | 说明 |
|------|------|------|
| `--behavior` | 是 | 用户观察到的行为描述 |
| `--subject` | 否 | 被分析对象的历史人物 ID |
| `--context` | 否 | 环境上下文信息 |

### 查询人物画像

```bash
python -m src.cli profile --subject colleague_A
```

参数说明：

| 参数 | 必填 | 说明 |
|------|------|------|
| `--subject` | 是 | 被查询对象的历史人物 ID |

画像输出包含基本信息、模式摘要（高频标签、重复机制、一句话描述）以及行为历史表格。当同一对象的行为记录达到 3 条及以上时，系统会自动生成或刷新 `pattern_summary`。

CLI 以 Markdown 格式输出结果，适合在终端直接阅读或复制到文档中。

---

## 画像查询接口（预留 MCP Tool）

未来若将画像查询暴露为 MCP Tool，建议按以下 Schema 注册：

```json
{
  "name": "behavior_psychology_profile",
  "description": "查询指定人物的行为画像，包括历史行为记录、高频标签、重复心理机制与模式摘要。适用于'帮我看看TA的历史模式'、'TA最近有什么变化'等场景。",
  "parameters": {
    "type": "object",
    "properties": {
      "subject_id": {
        "type": "string",
        "description": "被查询对象的历史人物 ID，用于定位画像记录。必填。"
      }
    },
    "required": ["subject_id"]
  }
}
```

返回结构示例：

```json
{
  "subject_id": "colleague_A",
  "alias": "",
  "created_at": "2026-05-25T00:43:02.250149",
  "updated_at": "2026-05-25T01:04:44.353892",
  "pattern_summary": "该对象在近期互动中反复表现出 control、anxiety、dominance_display 等行为模式，常见潜在机制包括 emotional_regulation、boundary_setting。需注意这些模式可能受情境因素影响，并非稳定人格特质。",
  "behavior_history": [
    {
      "timestamp": "2026-05-25T00:43:02.252734",
      "behavior_description": "同事在项目会议上连续打断我三次，且总是最后才回复我的消息",
      "tags": ["anxiety", "impatience", "control", "dominance_display", "low_priority"],
      "mechanisms": [],
      "confidence": 0.2,
      "universality_rating": "低"
    }
  ]
}
```
