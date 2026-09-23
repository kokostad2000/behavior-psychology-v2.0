# Security policy

## Supported version

Only the latest `main` revision is currently supported. The project is alpha software.

## Reporting

Do not open a public issue containing API keys, personal behavior descriptions, profile files, or provider responses. Contact the repository owner privately through the security contact configured on GitHub.

## Operational guidance

- Run the MCP server as a local, unprivileged user.
- Keep provider keys in environment variables or a user-readable configuration file; never commit `.env`.
- Keep profiles disabled unless the user explicitly opts in.
- Do not expose this stdio server as a shared multi-user service.
- Apply dependency updates only after the test, type-check, wheel-content, and audit checks pass.
