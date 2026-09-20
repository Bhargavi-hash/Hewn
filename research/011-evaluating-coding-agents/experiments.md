# Module 11 Experiments

## 011A — Metric Disagreement

### Question

Can the evaluation methodology distinguish protocol correctness,
mechanical correctness, task correctness, regression correctness, and
full behavioral success when those signals deliberately disagree?

### Motivation

Previous Hewn experiments demonstrated that intermediate metrics can
improve without behavioral success improving.

Before using a benchmark to evaluate an agent, the benchmark itself must
demonstrate that it distinguishes these outcomes.

011A therefore validates the measuring instrument without invoking a
model.

### Fixture

The fixture exposes two independent behaviors:

- `normalize_name(value)` implements the requested behavior;
- `stable_identifier(value)` represents unrelated existing behavior.

Initial behavior:

    normalize_name(" Alice ") == "Alice"
    stable_identifier("Alice") == "user:Alice"

The requested task is:

    Normalize names by stripping surrounding whitespace and converting
    them to lowercase.

The task oracle therefore requires:

    normalize_name(" Alice ") == "alice"

The regression oracle requires:

    stable_identifier("Alice") == "user:Alice"

### Conditions

#### A — protocol_failure

No valid edit is produced.

Expected:

- protocol valid: false
- edit applied: false
- task passes: false
- regression passes: true
- behavioral success: false

#### B — wrong_valid_patch

A syntactically and mechanically valid edit changes normalization in a
way that does not satisfy the requested behavior.

Expected:

- protocol valid: true
- edit applied: true
- task passes: false
- regression passes: true
- behavioral success: false

#### C — regression_patch

The requested normalization behavior becomes correct, but unrelated
existing behavior is broken.

Expected:

- protocol valid: true
- edit applied: true
- task passes: true
- regression passes: false
- behavioral success: false

#### D — correct_patch

The requested behavior becomes correct and existing behavior remains
correct.

Expected:

- protocol valid: true
- edit applied: true
- task passes: true
- regression passes: true
- behavioral success: true

### Primary metric

Behavioral success is:

    task_passes AND regression_passes

Protocol validity and edit application are explanatory metrics, not
substitutes for behavioral correctness.

### Measurements

For every condition record:

- protocol validity;
- edit application;
- task oracle result;
- regression oracle result;
- behavioral success.

Also report false-success counts for these proxy definitions:

- protocol-valid == success;
- edit-applied == success;
- task-only == success.

### Hypothesis

Protocol validity and edit application will each classify multiple
behaviorally unsuccessful cases as successful.

Task-only scoring will classify the regression-producing patch as
successful.

Only task correctness combined with regression correctness will match
the hidden expected classification for all four cases.

### Success criterion

The evaluator must reproduce the complete frozen expected matrix.

Any disagreement is an evaluator defect and must be corrected before the
instrument is used for agent evaluation.

### Model use

No model is invoked.

### Interpretation constraints

011A validates the benchmark's ability to represent deliberately
constructed outcome classes.

It does not estimate how frequently these failure modes occur in real
coding-agent runs.

It does not establish that the chosen regression suite is sufficient for
arbitrary repositories.

It does not compare Hewn with another coding agent.