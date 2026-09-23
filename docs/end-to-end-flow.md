# End-to-end flow — v2.1

## Default, non-persistent analysis

1. The caller submits an observable behavior and optional de-identified context.
2. Pydantic rejects unknown fields, invalid anonymous IDs, and oversized input.
3. The safety layer checks both fields for crisis, abuse, diagnostic or legal-determination intent, and obvious direct identifiers.
4. Boundary cases return safety-first guidance without calling the model.
5. Other input is serialized as JSON data beneath a system safety instruction. Instructions contained inside user text are not treated as application instructions.
6. The selected provider returns JSON.
7. The runtime validates types, lengths, confidence bounds, and the universality enum.
8. Tags and mechanisms outside the packaged knowledge base are removed. Diagnostic language is removed again after generation.
9. If fewer than two alternatives survive, local context rules and generic uncertainty explanations supplement them.
10. The response includes limitations and an explicit note that confidence is not calibrated.

No profile is created in this flow, even if `subject_id` is present.

## Explicit profile opt-in

Persistence requires all three fields:

```json
{
  "subject_id": "colleague_a",
  "request_id": "meeting-2026-09-22-01",
  "persist_profile": true
}
```

After a non-degraded analysis:

1. The profile store acquires an inter-process file lock.
2. It checks whether the same `request_id` already exists.
3. A duplicate is ignored and reported with `duplicate_request_ignored`.
4. A new entry is appended and the latest-five-record summary is recomputed.
5. Data is written to a uniquely named temporary file, flushed, and atomically replaced.
6. POSIX directory/file permissions are set to `0700`/`0600`.

Provider failures, invalid model output, and results without allowed tags are never persisted.

## Local data controls

```bash
bpa-cli profile --subject colleague_a
bpa-cli export-profile --subject colleague_a
bpa-cli forget-entry --subject colleague_a --request-id meeting-2026-09-22-01 --yes
bpa-cli delete-profile --subject colleague_a --yes
```

The profile store is single-user local storage. It is not an authenticated multi-tenant database.

## What is not implemented

- No embedding generation or semantic RAG retrieval.
- No automatic case archival.
- No multi-user authorization.
- No calibrated psychological probability model.
- No clinical or legal decision support.

`knowledge_base/cases.json` remains only as a non-runtime format example and is neither packaged nor read by the runtime.
