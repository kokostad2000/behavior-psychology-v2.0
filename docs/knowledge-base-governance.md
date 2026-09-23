# Knowledge-base governance

The JSON files are a constrained vocabulary, not a diagnostic handbook.

## Admission rules

A new behavior pattern or mechanism must:

1. describe an observable behavior or a clearly marked hypothesis;
2. avoid diseases, personality labels, moral judgments, and claims about intent;
3. include at least two plausible situational alternatives;
4. state the intended context and important counterexamples;
5. include a traceable reference pointer when it names a published construct;
6. identify cultural or population limits instead of treating one group as the norm;
7. receive review from at least two people, including a domain-qualified reviewer for psychology claims.

## Evidence status

The current `scientific_basis` fields are bibliography/search pointers only. They have not been graded through a systematic review. Runtime output must not present them as proof that a mechanism explains a particular person.

## Change review

Each knowledge-base change should add or update evaluation cases for:

- over-pathologizing;
- single-cause inference;
- cultural, gender, age, disability, or personality stereotyping;
- diagnostic-language leakage;
- disagreement between qualified reviewers.

## Removal and correction

Rules that produce repeated false positives or stigmatizing outputs should be disabled first, then reviewed. Stored user profiles do not automatically inherit revised labels; users can remove individual entries or delete the profile with the CLI.
