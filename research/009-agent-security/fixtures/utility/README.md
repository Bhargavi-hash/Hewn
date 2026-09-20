# 009D Authority Utility Fixtures

These fixtures form the frozen task corpus for Module 9 experiment 009D.

They evaluate legitimate coding-agent utility under different deterministic
authority granularities.

The corpus was frozen before the 009D evaluator was implemented or any model
was executed on these tasks.

## Task structure

The five tasks cover:

1. direct one-file modification;
2. repository discovery before modification;
3. modification followed by approved verification;
4. multi-file inspection with one-file modification;
5. legitimate multi-file modification followed by verification.

The tasks are intentionally small.

009D is intended to measure authority-policy friction rather than large-scale
repository reasoning ability.

## Hidden oracle

`manifest.json` contains evaluator-only information including:

- required capabilities;
- files relevant to the correct solution;
- files permitted to change;
- deterministic behavioral verification.

The hidden oracle must never be included in model-visible prompts or
repository evidence.

`required_files` identifies files that may legitimately need inspection. It
does not require the model to read every listed file.

`required_changed_files` identifies files that must change for the task to
count as behaviorally complete. This prevents behavioral-output checks from
accepting a semantically incomplete source change when multiple source files
are explicitly part of the requested modification.

`allowed_changed_files` defines the permitted mutation set for the exact-
resource policy and for unnecessary-modification measurement.

## Experimental integrity

Do not modify task wording, fixture contents, required capabilities, allowed
changed files, or behavioral verification after model execution begins.

If an evaluator defect is later discovered, record the defect explicitly and
preserve the original run rather than silently changing the frozen corpus.