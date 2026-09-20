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

## 011B — Repeated-Run Stability

### Question

How much can coding-agent outcomes vary across repeated runs when the
task, repository state, model configuration, agent configuration, and
nominal decoding settings are held fixed?

### Motivation

Many experiments in earlier Hewn modules used a single model run at
temperature zero.

Those runs are useful mechanism diagnostics, but a single observation
does not establish that the same agent configuration will reliably
produce the same outcome.

Sources of variation may remain even under nominally deterministic
decoding, including model-server behavior, prompt processing, agent
control flow, tool interaction, and runtime effects.

011B measures repeated-run stability before Hewn Bench adopts an
aggregation policy for model-based experiments.

### Model configuration

Use the existing local model configuration without modification:

- model: Qwen2.5-Coder-1.5B-Instruct GGUF
- quantization: Q4_K_M
- server: llama.cpp
- temperature: 0
- context window: 4096
- server threads: 4
- endpoint: http://127.0.0.1:8080

The server must remain running with the same configuration for the
complete experiment.

No prompt, tool, retrieval, context, or model configuration may be
changed between repetitions.

### Experimental unit

An experimental unit is one fresh execution of one frozen coding task.

Every repetition starts from an independently recreated baseline fixture.

No repository mutation from one repetition may reach another repetition.

### Repetitions

Evaluate three tasks.

Run each task five times.

Total model-based experimental units:

    3 tasks × 5 repetitions = 15 runs

Five repetitions are a diagnostic sample. They are not treated as a
precise estimate of a population success probability.

### Task classes

The frozen task set contains three qualitatively different tasks.

#### stability-001 — exact local edit

Repository behavior:

    greeting() == "hello"

Task:

    Change greeting() so it returns "hi" instead of "hello".
    Preserve all other behavior.

The target implementation is directly localizable from the task.

Behavioral oracle:

    greeting() == "hi"

Regression oracle:

    stable_identifier("Alice") == "user:Alice"

#### stability-002 — cross-file relationship

Repository behavior:

    settings.py defines DEFAULT_RETRIES = 2

    client.py imports DEFAULT_RETRIES and request_policy()
    returns it.

Task:

    Increase the default request retry count from 2 to 4.
    Preserve request_policy() as the consumer of the shared setting.

The task requires modifying the definition rather than hard-coding the
consumer.

Behavioral oracle:

    DEFAULT_RETRIES == 4
    request_policy() == 4

Structural regression oracle:

    client.py still imports DEFAULT_RETRIES from sample.settings

Regression oracle:

    stable_identifier("Alice") == "user:Alice"

#### stability-003 — semantic behavior edit

Repository behavior:

    normalize_name(value) strips surrounding whitespace.

Task:

    Normalize names by stripping surrounding whitespace and converting
    non-empty names to lowercase. Empty or whitespace-only names should
    return None.

Behavioral oracles:

    normalize_name(" Alice ") == "alice"
    normalize_name(" BOB ") == "bob"
    normalize_name("   ") is None

Regression oracle:

    stable_identifier("Alice") == "user:Alice"

The task describes behavior rather than an exact source replacement.

### Hidden evaluator information

The following must remain evaluator-only:

- behavioral oracle implementation;
- regression oracle implementation;
- structural oracle implementation;
- expected changed files;
- patch classification;
- final success calculation.

The model receives only the task request and normal Hewn repository
context/tools.

### Reset procedure

Before every repetition:

1. create a fresh temporary fixture;
2. populate it from the frozen task baseline;
3. construct fresh repository/retrieval state;
4. construct a fresh Hewn session;
5. run the agent;
6. evaluate the resulting repository;
7. record the result;
8. destroy the temporary fixture.

No memory is shared between repetitions.

### Primary outcome

A run is behaviorally successful only when:

    task oracle passes
    AND
    all required regression oracles pass

For stability-002, the structural oracle is also required.

Protocol validity, edit application, or final-response production alone
does not count as success.

### Per-run measurements

Record at least:

- task ID;
- repetition number;
- behavioral success;
- task oracle result;
- regression oracle result;
- structural oracle result where applicable;
- protocol validity;
- final response observed;
- model calls;
- tool calls;
- tool names;
- edit attempts;
- successful edit applications;
- execution calls;
- context character count;
- wall-clock duration;
- changed files;
- final repository diff;
- SHA-256 hash of the normalized final diff.

A run that produces no diff must still receive a deterministic diff hash.

### Patch normalization

The patch hash is computed from a deterministic unified diff between the
fresh baseline fixture and the final fixture.

Normalize repository-relative paths and line endings before hashing.

Do not classify different patch hashes as better or worse merely because
they differ.

Patch diversity is a stability measurement.

### Aggregate reporting

For each task report:

- behavioral successes out of 5;
- protocol-valid runs out of 5;
- runs producing edits out of 5;
- distinct final patch hashes;
- model-call range;
- tool-call range;
- wall-time range.

Across all 15 runs report raw counts.

Do not use the 15 runs as independent samples of one homogeneous task
distribution because the experiment contains only three task classes.

### Stability interpretation

A task is observationally stable in this diagnostic if all five
repetitions agree on behavioral success or failure.

A task is behaviorally variable if both successful and unsuccessful runs
occur.

Patch variability and behavioral variability are reported separately.

Five identical outcomes do not prove deterministic behavior.

### Statistical reporting

Counts are primary.

A value such as:

    3/5 runs succeeded

may additionally be described as an observed 60% success fraction, but
it must not be presented as a precise estimate of general success
probability.

No significance test is planned for 011B.

No cross-agent comparison is made.

### Failure handling

Every attempted repetition remains in the denominator.

This includes:

- protocol failures;
- model errors;
- timeouts;
- rejected edits;
- stagnation;
- incorrect finalization;
- zero-edit runs;
- execution failures.

The evaluator must record the failure class rather than silently retrying
the experimental unit.

Infrastructure failure before the model run begins may be retried only
when no experimental observation was produced, and such retries must be
documented.

### No tuning after observation

After the first model repetition is observed:

- task wording is frozen;
- fixtures are frozen;
- prompts are frozen;
- retrieval is frozen;
- tool policy is frozen;
- maximum turns are frozen;
- evaluator oracles are frozen.

A genuine evaluator defect may be corrected, but the affected run must
be versioned or rerun as a new experiment rather than silently replaced.

### Success criterion

011B succeeds as an experiment if all 15 frozen repetitions are recorded
with sufficient information to determine:

1. whether behavioral outcomes vary within a task;
2. whether patch outputs vary within a task;
3. whether protocol behavior varies within a task;
4. how much model/tool usage and wall time vary.

The experiment does not require the agent to solve any minimum number of
tasks.

Zero behavioral successes remains a valid result.

### Interpretation constraints

011B measures stability of one Hewn/model/server configuration on three
small tasks.

It does not establish general coding-agent reliability.

Temperature zero must not be described as guaranteeing deterministic
behavior.

Repeated failure is stability, not capability.

Repeated success is evidence of consistency on the tested fixture, not
general competence.

## 011C — Regression-aware scoring

### Research question

Can task-local verification incorrectly classify a patch as successful
when the requested behavior passes but existing behavior outside the
requested change regresses?

### Purpose

011A established that task correctness and regression correctness are
distinct evaluation layers.

011C tests that distinction directly by comparing two scoring rules over
controlled patches:

1. task-only success;
2. regression-aware behavioral success.

The experiment is deterministic and does not use a language model. Its
purpose is to validate the benchmark scoring rule, not to estimate how
frequently coding agents introduce regressions.

### Frozen fixture

The fixture contains a small normalization module:

```python
def normalize_name(value: str) -> str | None:
    normalized = value.strip()
    if not normalized:
        return None
    return normalized


def stable_identifier(value: str) -> str:
    return f"user:{value}"
```

The requested task is:

> Normalize non-empty names by stripping surrounding whitespace and
> converting them to lowercase. Empty or whitespace-only names should
> continue to return `None`. Preserve all other behavior.

### Hidden evaluator oracles

The requested-behavior oracle checks:

```python
normalize_name(" Alice ") == "alice"
normalize_name(" BOB ") == "bob"
normalize_name("   ") is None
```

The regression oracle checks:

```python
stable_identifier("Alice") == "user:Alice"
stable_identifier("BOB") == "user:BOB"
```

The regression oracle is evaluator-only. It is not part of the task
description supplied to an agent in any later model-based experiment.

### Frozen conditions

Four deterministic candidate implementations are evaluated.

#### A — no-op

`normalize_name` remains unchanged and `stable_identifier` remains
unchanged.

Expected:

- task passes: false
- regression passes: true
- task-only success: false
- behavioral success: false

#### B — correct task, regression introduced

`normalize_name` correctly strips and lowercases non-empty values and
preserves the empty-input behavior.

`stable_identifier` is incorrectly changed to lowercase its value:

```python
def stable_identifier(value: str) -> str:
    return f"user:{value.lower()}"
```

Expected:

- task passes: true
- regression passes: false
- task-only success: true
- behavioral success: false

This condition is the central false-success case.

#### C — wrong task, regression preserved

`normalize_name` strips whitespace but does not lowercase non-empty
values.

`stable_identifier` remains unchanged.

Expected:

- task passes: false
- regression passes: true
- task-only success: false
- behavioral success: false

#### D — correct task, regression preserved

`normalize_name` correctly strips and lowercases non-empty values and
preserves the empty-input behavior.

`stable_identifier` remains unchanged.

Expected:

- task passes: true
- regression passes: true
- task-only success: true
- behavioral success: true

### Scoring rules

Task-only scoring is:

```text
task_only_success = task_passes
```

Regression-aware behavioral scoring is:

```text
behavioral_success = task_passes AND regression_passes
```

No weighted score is used.

A task failure cannot be compensated for by passing regressions, and a
regression cannot be compensated for by satisfying the requested
behavior.

### Expected matrix

| Condition | Task passes | Regression passes | Task-only success | Behavioral success |
|---|---:|---:|---:|---:|
| A — no-op | false | true | false | false |
| B — task correct, regression | true | false | true | false |
| C — task wrong, regression preserved | false | true | false | false |
| D — fully correct | true | true | true | true |

### Primary measurement

Count false successes produced by task-only scoring relative to the
frozen regression-aware behavioral classification.

Expected:

```text
task-only false successes: 1
```

The false success should be condition B.

Also record:

- expected matrix matches;
- task-only successes;
- behavioral successes;
- false successes caused by omitted regression checking.

### Success criterion

011C succeeds as an evaluation-methodology experiment if:

1. all four observed task/regression classifications match the frozen
   expected matrix;
2. task-only scoring counts condition B as successful;
3. regression-aware behavioral scoring rejects condition B;
4. condition D remains successful under regression-aware scoring.

Expected aggregate:

```text
expected matrix matched: 4/4
task-only successes: 2/4
behavioral successes: 1/4
task-only false successes: 1
```

### Interpretation constraints

This experiment demonstrates that task-local verification can produce a
false success when a deliberately constructed regression is outside the
task oracle.

It does not estimate the frequency with which coding agents introduce
regressions.

The fixture contains one deliberately selected unrelated behavior.
Passing the regression oracle does not establish absence of all possible
regressions.

The experiment therefore supports regression-aware evaluation as a
measurement requirement, not a claim that any finite regression suite
proves complete correctness.

### Frozen implementation rule

After this design is committed, the candidate implementations, task
oracle, regression oracle, expected matrix, and scoring definitions must
not be changed in response to observed evaluator output.

If the evaluator itself contains a defect, preserve the affected run,
document the defect, correct only the evaluator implementation, and
execute a new run.