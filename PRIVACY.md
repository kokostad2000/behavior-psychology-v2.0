# Privacy model

This project handles potentially sensitive descriptions about other people.

- The behavior description and optional context are sent to the configured LLM provider.
- Callers should remove names, contact details, account identifiers, medical details, and other unnecessary identifiers before submission.
- The local safety layer blocks obvious email, mainland-China mobile, and ID-number formats before a provider call. This is a narrow safeguard, not a complete de-identification system.
- The MCP server does not log tool arguments or model output.
- Local profiles are disabled by default. A write requires `persist_profile=true`, an anonymous `subject_id`, and a stable `request_id`.
- Local profiles are stored outside the source/install directory with directory mode `0700` and file mode `0600` on POSIX systems.
- `bpa-cli export-profile`, `forget-entry`, and `delete-profile` provide access, correction-by-removal, and deletion.
- Profiles are intended only for a single-user local environment. This repository does not provide multi-tenant authentication or authorization.
- Model providers may retain or process submitted data under their own terms. Review the selected provider's policy before using real personal data.

Do not use this project for employee screening, disciplinary decisions, medical or legal decisions, surveillance, or diagnosis.
