# behavior-psychology 2.1

一个实验性的行为假设整理工具：根据用户提供的有限观察，输出多个可能解释、非诊断机制和明确局限。

> **Alpha 状态。** 本项目没有经过临床验证，置信度未经统计校准，不得用于诊断、招聘、纪律处分、医疗/法律决定、伴侣监控或其他高风险决策。

## 隐私摘要

- 行为描述和上下文会发送给所配置的 LLM 供应商；提交前请删除姓名、联系方式等标识符。系统会在调用供应商前拦截明显的邮箱、中国大陆手机号和身份证号格式，但这不是完整的脱敏器。
- MCP 不记录工具参数或模型输出。
- 人物画像默认关闭。只有显式传入 `--save-profile` / `persist_profile=true` 才会写入本机。
- 画像使用匿名 `subject_id`，支持导出、按请求删除和整库删除。

完整说明见 [PRIVACY.md](PRIVACY.md)。

## 安装

```bash
python -m pip install -e ".[dev]"
cp .env.example .env
```

选择一个供应商密钥：

```bash
DEEPSEEK_API_KEY=...
# 或 DASHSCOPE_API_KEY=...
# 或 OPENAI_API_KEY=...
```

默认模型分别为 `deepseek-flash`、`qwen-plus`、`gpt-4o-mini`。可通过 `BEHAVIOR_PSYCHOLOGY_PROVIDER` 和 `BEHAVIOR_PSYCHOLOGY_MODEL` 覆盖。配置解析只有一套实现，环境变量和 `~/.openclaw/openclaw.json` 使用相同逻辑。

## CLI

默认只分析、不保存：

```bash
bpa-cli analyze \
  --behavior "同事在项目会议中多次打断我的发言" \
  --context "项目周会，时间较紧"
```

显式同意保存画像：

```bash
bpa-cli analyze \
  --behavior "同事在项目会议中多次打断我的发言" \
  --subject colleague_a \
  --request-id meeting-2026-09-22-01 \
  --save-profile
```

画像控制：

```bash
bpa-cli profile --subject colleague_a
bpa-cli export-profile --subject colleague_a
bpa-cli forget-entry --subject colleague_a --request-id meeting-2026-09-22-01 --yes
bpa-cli delete-profile --subject colleague_a --yes
```

本地画像默认位于操作系统的用户数据目录，也可通过 `BEHAVIOR_PSYCHOLOGY_DATA_DIR` 指定私有目录。

## MCP

安装后使用入口：

```bash
bpa-mcp
```

从源码运行：

```bash
python -m src.mcp_server
```

工具名固定为 `analyzing-behavior`。Server 支持初始化、`ping`、`tools/list`、`tools/call`、初始化通知和取消通知；通知不产生 JSON-RPC 响应。输入单条上限为 1 MiB，业务字段另有限长。

## 实际处理流程

1. 同时检查行为描述与上下文中的诊断、法律、危机、虐待边界和明显的直接标识符。
2. 用 system message 将安全规则与用户数据隔离。
3. 调用配置的 OpenAI-compatible Chat Completions API。
4. 用 Pydantic 验证 JSON 结构。
5. 过滤知识库之外的标签/机制及临床标签。
6. 替代解释不足时，从本地规则库补足至少两种视角。
7. 仅在用户明确同意后，以幂等方式写入本地画像。

项目当前**不使用 Embedding 或 RAG**；`knowledge_base/cases.json` 只是未接入运行时的格式示例。

## 开发验证

```bash
python -m pytest
mypy src
ruff check src tests
python -m pip wheel . --no-deps -w dist
```

CI 在 Python 3.10–3.12 上运行测试、覆盖率、类型检查、lint、依赖审计，并验证 wheel 含有三个运行时知识库文件。

## 已知局限

- 输入通常来自单方叙述，不能证明他人的真实动机。
- 置信度是模型的未校准相对评分，不是统计概率。
- 知识库中的理论名称是检索线索，不等同于系统综述或临床证据。
- 危机提示不能替代当地紧急服务。
- 本地画像只适用于单用户环境；没有多租户授权层。

## 许可证

[MIT](LICENSE)
