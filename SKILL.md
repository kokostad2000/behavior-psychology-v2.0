---
name: analyzing-behavior
description: >
  Analyzes user-described behaviors or social interactions to identify
  possible psychological mechanisms, cognitive patterns, and social factors.
  Use when the user asks to analyze someone's behavior, understand why
  someone acted a certain way, interpret social dynamics, or get
  alternative explanations for an observed action. Returns a structured
  report with tags, mechanisms, alternative explanations, confidence
  score, and universality rating.
---

# Skill: analyzing-behavior

## When to use

- The user asks to "analyze" a behavior, interaction, or social situation.
- The user asks "why did someone act this way" or "what's going on here".
- The user describes an interpersonal conflict and wants interpretation.
- The user asks for alternative perspectives on someone's actions.

## When NOT to use

- The user requests a clinical diagnosis or assessment of a mental disorder.
- The user asks for a legal judgment or liability determination.
- The user describes self-harm, suicidal ideation, or abuse — escalate to
  appropriate crisis resources instead.
- The input is purely factual (e.g., "What time is it?") with no behavior
  to analyze.

## Steps

- [ ] 1. Parse the input into `AnalysisRequest`.
  - Required: `behavior_description`
  - Optional: `context`, `subject_id`, `request_id`
- [ ] 2. Boundary check: invoke `_check_boundary_violation()` to intercept
  clinical diagnosis, legal judgment, or crisis-related requests.
- [ ] 3. LLM direct analysis: invoke `_llm_analyze()` to get behavior tags,
  psychological mechanisms, alternative explanations, confidence, and
  universality rating from the LLM.
- [ ] 4. Assemble `AnalysisResponse` from the LLM result.
- [ ] 5. If `subject_id` is provided, update the subject's profile and
  regenerate `pattern_summary` when history >= 3 entries.
- [ ] 6. Return `AnalysisResponse`.

## Input

`AnalysisRequest` fields:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `behavior_description` | string | Yes | Observed behavior text. |
| `context` | string | No | Environment, time, place, trigger event. |
| `subject_id` | string | No | Persistent identifier for longitudinal tracking. |
| `request_id` | string | No | Trace / idempotency ID. |

## Output

`AnalysisResponse` fields:

| Field | Type | Description |
|-------|------|-------------|
| `tags` | list[string] | Matched behavior tags. |
| `psychological_mechanisms` | list[object] | `{name, explanation}` |
| `alternative_explanations` | list[object] | `{perspective, reasoning}` |
| `confidence` | number | 0.0–1.0 overall confidence. |
| `universality_rating` | string | 高 / 中 / 低 |
| `disclaimer` | string | Fixed disclaimer text. |
| `subject_id` | string | Echo of request `subject_id`. |
| `pattern_summary` | string | Pattern summary when history >= 3 entries. |
| `blocked` | boolean | Whether analysis was blocked by boundary check. |
| `degradation_flags` | list[string] | Degradation tags (e.g., llm_no_tags, profile_update_failed). |

## References

- [docs/api_specs.md](docs/api_specs.md) — API schema, MCP / OpenClaw / CLI
  integration guide.
- [knowledge_base/behavior_patterns.json](knowledge_base/behavior_patterns.json)
  — Behavior pattern library.
- [knowledge_base/psychological_mechanisms.json](knowledge_base/psychological_mechanisms.json)
  — Psychological mechanism library.
- [knowledge_base/alternative_explanations.json](knowledge_base/alternative_explanations.json)
  — Alternative-explanation rules.

## Failure Strategy

| Stage | Failure | Degradation |
|-------|---------|-------------|
| LLM API call | No DEEPSEEK_API_KEY configured | Return empty result with warning; suggest setting env var. |
| LLM API call | API error or timeout | Return empty result with warning; suggest checking network / key balance. |
| Profile update | Disk I/O error | Log warning; analysis result unaffected. |

## Constraints

- Do not output clinical diagnostic labels (e.g., NPD, BPD, depression).
- Do not present low-confidence interpretations as facts.
- Always include the fixed disclaimer in the response.
- Log all degradations in Chinese with impact and remediation guidance.
