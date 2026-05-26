# behavior-psychology-v2.0

基于 LLM 的行为心理分析 Skill — 对用户描述的行为或社交互动进行结构化心理分析，输出行为标签、心理机制、替代解释与置信度评估。

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env，填入你的 DeepSeek API Key
# DEEPSEEK_API_KEY=sk-xxx
```

### 3. 运行 CLI 分析

```bash
python -m src.cli analyze \
  --behavior "同事在项目会议上连续打断我三次" \
  --subject colleague_A \
  --context "工作群聊"
```

## 目录结构

```
behavior-psychology-v2.0/
├── src/                          # 核心源码
│   ├── analyzer.py               # 默认分析器（LLM 直接推理）
│   ├── schemas.py                # 请求/响应 Pydantic 模型
│   ├── interfaces.py             # 抽象基类
│   ├── cli.py                    # 命令行入口
│   ├── mcp_server.py             # MCP Server 适配层
│   └── openclaw_tool.py          # OpenClaw 插件适配层
├── knowledge_base/               # 知识库（JSON）
│   ├── behavior_patterns.json    # 行为标签库
│   ├── psychological_mechanisms.json  # 心理机制库
│   └── alternative_explanations.json  # 替代解释规则
├── tests/                        # 测试用例
├── docs/                         # 文档
│   ├── api_specs.md              # API 规范与接入指南
│   └── SKILL.md                  # Skill 元数据与使用说明
├── SKILL.md                      # Skill 根级元数据
├── pyproject.toml                # 项目配置
└── requirements.txt              # 依赖列表
```

## 接入方式

### MCP（推荐）

通过 stdio 与 Claude Desktop、Cursor 等客户端通信：

```bash
python -m src.mcp_server
```

配置示例见 [docs/api_specs.md](docs/api_specs.md#mcp-接入指南)。

### OpenClaw

```python
from src.openclaw_tool import register_tools, handle_tool_call

tools = register_tools()
for tool in tools:
    agent.register_tool(tool, handler=handle_tool_call)
```

### CLI

```bash
# 行为分析
python -m src.cli analyze --behavior "..." --subject id --context "..."

# 查询画像
python -m src.cli profile --subject id
```

## 模型说明

- **默认模型**: DeepSeek `deepseek-chat`（通过 OpenAI 兼容接口调用）
- **推理方式**: LLM 直接分析，无需 Embedding 或 RAG
- **知识库作用**: 作为 Prompt 上下文注入，辅助 LLM 生成结构化标签与机制

## 许可证

MIT
