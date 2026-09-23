---
name: analyzing-behavior
description: >
  Organizes multiple non-diagnostic hypotheses for a user-described behavior or
  social interaction. Use when the user asks for alternative interpretations
  of observable behavior. Do not use for diagnosis, crisis intervention, legal
  determinations, surveillance, employment decisions, or claims about another
  person's true motives.
---

# Analyzing behavior

## Required boundaries

- Treat the input as one person's limited observation, not objective evidence.
- Never diagnose a disorder, infer a stable personality, or claim to know the subject's motive.
- Do not use model confidence as a probability, clinical score, or measurement.
- For self-harm, suicide, abuse, or immediate danger, stop behavioral inference and provide safety-first guidance.
- For legal or clinical determinations, state the boundary and redirect to a qualified professional.
- Do not use this tool for hiring, discipline, medical/legal decisions, partner monitoring, or profiling minors.

## Privacy

- Ask the user to remove direct identifiers and unnecessary sensitive details.
- Explain that the description and context are sent to the configured model provider.
- Do not save a profile by default.
- Save only when the user explicitly opts in and supplies an anonymous `subject_id` plus stable `request_id`.
- Support profile inspection, export, correction-by-removal, and deletion.

## Workflow

1. Parse `AnalysisRequest` and enforce field size limits.
2. Check both `behavior_description` and `context` with the safety boundary.
3. Send the observation as untrusted JSON data under a higher-priority safety instruction.
4. Validate the model JSON against the internal schema.
5. Keep only tags and mechanisms present in the packaged knowledge base.
6. Remove clinical labels and supplement fewer than two alternatives with non-diagnostic context explanations.
7. Return limitations and an uncalibrated-confidence notice.
8. If and only if `persist_profile=true`, store the result idempotently outside the package directory.

## Input

| Field | Required | Limit | Meaning |
|---|---:|---:|---|
| `behavior_description` | yes | 2–4000 chars | Observable behavior, preferably de-identified |
| `context` | no | 4000 chars | De-identified situation and relationship context |
| `subject_id` | for persistence | 128 chars | Anonymous local identifier |
| `request_id` | for persistence | 128 chars | Stable idempotency key |
| `persist_profile` | no | boolean | Explicit local-storage opt-in; default `false` |

## Output expectations

- At least two alternative explanations for non-blocked results.
- Per-mechanism confidence and universality labels, both clearly framed as hypotheses.
- Global `confidence_basis`, `limitations`, `disclaimer`, and `degradation_flags`.
- `blocked` and `safety_category` when a safety boundary is triggered.
- `profile_persisted` so the caller can verify whether a local write occurred.

## Failure behavior

- Invalid model JSON: return no mechanisms, `confidence=0`, and `llm_invalid_output`.
- Provider/network failure: return no mechanisms, `confidence=0`, and `llm_api_error`.
- Degraded outputs are never written to a profile.
- Profile I/O failure does not discard the analysis; return `profile_update_failed`.
