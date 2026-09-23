# API specification — behavior-psychology 2.1

## Request

```json
{
  "behavior_description": "同事在会议中多次打断我的发言",
  "context": "项目周会，时间较紧",
  "subject_id": "colleague_a",
  "request_id": "meeting-2026-09-22-01",
  "persist_profile": false
}
```

| Field | Required | Rule |
|---|---:|---|
| `behavior_description` | yes | 2–4000 characters |
| `context` | no | at most 4000 characters; de-identify before sending |
| `subject_id` | only for persistence | anonymous `[A-Za-z0-9_.:-]+`, at most 128 characters |
| `request_id` | only for persistence | stable idempotency key, at most 128 characters |
| `persist_profile` | no | defaults to `false`; `true` requires `subject_id` and `request_id` |

Unknown fields are rejected.

## Response

```json
{
  "tags": ["conversation_interruption", "turn_taking_overlap"],
  "psychological_mechanisms": [
    {
      "name": "situational_stress",
      "explanation": "时间压力可能使发言节奏加快",
      "confidence": 0.45,
      "universality_rating": "中"
    }
  ],
  "alternative_explanations": [
    {"perspective": "时间压力", "reasoning": "会议时间不足可能使发言更急促"},
    {"perspective": "沟通习惯", "reasoning": "某些团队允许更频繁的交叉发言"}
  ],
  "confidence": 0.55,
  "confidence_basis": "模型基于有限文本的未校准估计，不是测量结果或事实概率。",
  "universality_rating": "中",
  "limitations": ["输入来自单方、有限的行为描述"],
  "disclaimer": "本分析只提供待验证的行为假设……",
  "subject_id": null,
  "pattern_summary": null,
  "profile_persisted": false,
  "blocked": false,
  "safety_category": null,
  "degradation_flags": []
}
```

`confidence` and per-mechanism confidence are uncalibrated model estimates. They are not probabilities or clinical scores.

## MCP

Tool name: `analyzing-behavior`.

Recommended installed command:

```json
{
  "mcpServers": {
    "behavior-psychology": {
      "command": "bpa-mcp",
      "env": {"DEEPSEEK_API_KEY": "set-in-your-local-config"}
    }
  }
}
```

From a source checkout use `python -m src.mcp_server`; direct execution of `src/mcp_server.py` is not supported.

Supported legacy-handshake methods:

- `initialize`
- `ping`
- `tools/list`
- `tools/call`
- `notifications/initialized` (no response)
- `notifications/cancelled` (no response)

The stdio transport accepts newline-delimited JSON-RPC 2.0 messages up to 1 MiB. Tool inputs have the smaller field limits listed above. Errors returned to clients use stable messages and do not include host paths or exception strings.

## OpenClaw

```python
from src.openclaw_tool import handle_tool_call, register_tools

for tool in register_tools():
    agent.register_tool(tool, handler=handle_tool_call)
```

OpenClaw, MCP, and CLI all use the same configuration resolver in `src/config.py`.

## Degradation flags

| Flag | Meaning |
|---|---|
| `llm_api_error` | provider/network call failed |
| `llm_invalid_output` | model output failed strict schema validation |
| `unknown_tags_filtered` | one or more tags were outside the knowledge base |
| `unknown_mechanisms_filtered` | one or more mechanisms were outside the knowledge base |
| `clinical_output_filtered` | diagnostic language was removed |
| `alternatives_supplemented` | local non-diagnostic alternatives were added |
| `profile_not_saved_degraded` | a degraded result was deliberately not persisted |
| `duplicate_request_ignored` | the same profile `request_id` was already stored |
| `profile_update_failed` | analysis succeeded but local profile storage failed |
