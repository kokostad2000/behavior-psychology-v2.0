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
- [ ] 2. Retrieve similar cases via semantic search (embedding similarity).
- [ ] 3. Match behavior tags from `behavior_patterns.json` using keyword
  and case-based signals.
- [ ] 4. Lookup psychological mechanisms from `psychological_mechanisms.json`
  based on matched tags.
- [ ] 5. Lookup alternative explanations from `alternative_explanations.json`
  using tag + context keyword filtering.
- [ ] 6. Compute `confidence` (0.0–1.0) and `universality_rating`
  (高 / 中 / 低).
- [ ] 7. If `confidence < 0.5` or no mechanisms matched, trigger LLM deep
  analysis for semantic enhancement.
- [ ] 8. If `subject_id` is provided, update the subject's profile and
  regenerate `pattern_summary` when history >= 3 entries.
- [ ] 9. Assemble and return `AnalysisResponse`.

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
| `llm_insights` | object | Optional deep-analysis enrichment. |

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
| Embedding generation | openai SDK missing or API error | Skip semantic search; rely on keyword matching only (lower precision). |
| Case retrieval | Empty cases.json or all embeddings empty | Return empty similar_cases; confidence derived from tags + mechanisms only. |
| Tag matching | No keywords hit | Tags = empty; mechanisms = empty; confidence will be low; LLM deep analysis triggered. |
| LLM deep analysis | API error or timeout | Skip enrichment; base response still returned with low-confidence warning. |
| Profile update | Disk I/O error | Log warning; analysis result unaffected. |

## Constraints

- Do not output clinical diagnostic labels (e.g., NPD, BPD, depression).
- Do not present low-confidence interpretations as facts.
- Always include the fixed disclaimer in the response.
- Log all degradations in Chinese with impact and remediation guidance.
