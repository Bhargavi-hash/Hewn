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

## 011D — Efficiency accounting

### Research question

Can Hewn Bench account for the additional computational and interaction
cost of an agent strategy without allowing lower cost to compensate for
incorrect behavior or higher cost to masquerade as greater capability?

### Motivation

Earlier Hewn experiments introduced mechanisms that can increase agent
cost:

- additional retrieved context;
- additional model calls;
- planning calls;
- reviewer calls;
- tool calls;
- execution and verification;
- repair iterations.

Some mechanisms improved intermediate metrics without improving
behavioral success.

A benchmark therefore needs to measure both correctness and cost while
keeping them conceptually separate.

011D validates the accounting model before Hewn Bench uses it on larger
agent comparisons.

### Principle

Correctness is evaluated first.

Efficiency describes the cost of obtaining that outcome.

Efficiency must not convert an incorrect solution into a successful one.

The benchmark therefore does not define a weighted score such as:

```text
success - latency_penalty - token_penalty
```

and does not allow cheap failure to outrank correct behavior merely
because it consumed fewer resources.

### Experimental method

011D is a deterministic evaluator experiment.

No language model is invoked.

Four synthetic run records represent different combinations of
behavioral outcome and resource usage.

The experiment validates aggregation and classification only. It does
not estimate the real cost of any model or agent architecture.

### Frozen resource fields

Each run records:

- model calls;
- tool calls;
- execution calls;
- context characters;
- wall time in seconds.

Token counts are intentionally excluded from this experiment because
the current Hewn model interface does not expose a uniform measured
token-usage field.

A later benchmark may add measured prompt and completion tokens when
the model backend exposes them reliably.

No character-to-token conversion is used as a substitute for measured
token usage.

### Frozen conditions

#### A — correct, lower cost

```text
behavioral_success = true
model_calls = 2
tool_calls = 2
execution_calls = 1
context_chars = 1000
wall_time_seconds = 4.0
```

#### B — correct, higher cost

```text
behavioral_success = true
model_calls = 5
tool_calls = 6
execution_calls = 3
context_chars = 3000
wall_time_seconds = 12.0
```

#### C — incorrect, lower cost

```text
behavioral_success = false
model_calls = 1
tool_calls = 0
execution_calls = 0
context_chars = 500
wall_time_seconds = 2.0
```

#### D — incorrect, higher cost

```text
behavioral_success = false
model_calls = 4
tool_calls = 5
execution_calls = 2
context_chars = 2500
wall_time_seconds = 10.0
```

### Outcome classes

Each run is first classified only by behavioral correctness:

```text
successful
unsuccessful
```

Resource measurements do not participate in this classification.

Expected:

| Condition | Behavioral class |
|---|---|
| A | successful |
| B | successful |
| C | unsuccessful |
| D | unsuccessful |

### Efficiency comparison rule

Efficiency comparisons are valid only within an explicitly selected
outcome class or when correctness is reported alongside the cost.

For the successful class:

- A uses fewer model calls than B;
- A uses fewer tool calls than B;
- A uses fewer execution calls than B;
- A uses fewer context characters than B;
- A has lower wall time than B.

Therefore A is lower-cost than B on every frozen resource dimension.

For the unsuccessful class:

- C is lower-cost than D on every frozen resource dimension.

This does not make C a better coding solution than A or B.

### Dominance relation

For two runs with the same behavioral classification, run X
resource-dominates run Y if X uses no more of every measured resource
and strictly less of at least one measured resource.

Measured dimensions are:

```text
model_calls
tool_calls
execution_calls
context_chars
wall_time_seconds
```

Under the frozen records:

```text
A resource-dominates B
C resource-dominates D
```

No cross-correctness dominance claim is made.

In particular:

```text
C does not dominate A
```

even though C is cheaper, because C is behaviorally unsuccessful and A
is successful.

### Aggregate accounting

The evaluator records totals and arithmetic means for each resource
dimension across all four synthetic runs.

Frozen expected totals:

```text
model_calls = 12
tool_calls = 13
execution_calls = 6
context_chars = 7000
wall_time_seconds = 28.0
```

Frozen expected means:

```text
model_calls = 3.0
tool_calls = 3.25
execution_calls = 1.5
context_chars = 1750.0
wall_time_seconds = 7.0
```

The evaluator also reports resource aggregates separately for
successful and unsuccessful runs.

Successful totals:

```text
model_calls = 7
tool_calls = 8
execution_calls = 4
context_chars = 4000
wall_time_seconds = 16.0
```

Unsuccessful totals:

```text
model_calls = 5
tool_calls = 5
execution_calls = 2
context_chars = 3000
wall_time_seconds = 12.0
```

### Expected measurements

The evaluator must establish:

```text
behavioral classifications matched: 4/4
successful runs: 2/4
A dominates B within successful class: true
C dominates D within unsuccessful class: true
C dominates A across correctness classes: not evaluated
aggregate accounting matched: true
```

### Success criterion

011D succeeds as an evaluation-methodology experiment if:

1. all four behavioral classifications match the frozen expectations;
2. resource accounting matches the frozen totals and means;
3. A is identified as resource-dominating B;
4. C is identified as resource-dominating D;
5. the evaluator refuses to apply the resource-dominance relation
   across different behavioral classes;
6. no combined quality/cost score is produced.

### Interpretation constraints

011D validates an accounting and comparison rule over synthetic records.

It does not show that any Hewn strategy is actually faster or cheaper.

The selected resource dimensions are not exhaustive.

Wall time is hardware- and environment-dependent in real experiments.

Context characters measure supplied context size, not tokenizer-level
prompt cost.

Model-call counts do not imply equal inference cost across different
models.

Tool-call counts do not imply equal cost across different tools.

Execution-call counts do not imply equal runtime across different
commands.

Accordingly, Hewn Bench should retain raw resource dimensions rather
than hiding them behind one universal efficiency score.

### Design implication

Hewn Bench should treat evaluation as two related questions:

```text
1. Did the agent solve the task without detected regression?
2. What resources did it consume to obtain that outcome?
```

The first is a correctness question.

The second is an efficiency question.

Efficiency should help compare strategies with equivalent observed
correctness, but it must not redefine correctness.

### Frozen implementation rule

After this design is committed, the four synthetic records, measured
resource dimensions, expected aggregates, behavioral classifications,
and dominance definition must not be changed in response to evaluator
output.

If an evaluator implementation defect is discovered, preserve the
affected run, document the defect, correct only the evaluator, and
execute a new run.

## 011E — Benchmark integrity and contamination

### Research question

Can Hewn Bench mechanically separate agent-visible task information from
evaluator-only information so that hidden oracles, expected outputs, and
benchmark metadata cannot accidentally become part of the agent's
evaluation context?

### Motivation

A benchmark result is not meaningful if information used to evaluate a
solution is accidentally exposed to the system being evaluated.

For a coding-agent benchmark, information can reach the agent through
multiple surfaces:

- the user request;
- repository files;
- retrieved repository context;
- tool definitions;
- tool results;
- generated system or control instructions.

Evaluator-only information may include:

- hidden behavioral assertions;
- hidden regression assertions;
- expected outputs;
- expected changed files;
- expected patches;
- benchmark classifications;
- scoring metadata.

011E tests whether the benchmark representation can make that boundary
explicit and mechanically enforceable.

### Scope

011E is a deterministic benchmark-instrument experiment.

No language model is invoked.

The experiment does not attempt to detect contamination in arbitrary
external benchmark datasets or model pretraining.

It tests only contamination introduced by Hewn's own benchmark
construction and agent-input assembly.

### Principle

Benchmark data is classified before execution as either:

```text
agent-visible
```

or:

```text
evaluator-only
```

Evaluator-only fields must not be included in the assembled
agent-visible benchmark payload.

The evaluator may consume both classes after the agent run.

### Frozen benchmark record

The synthetic benchmark case contains the following agent-visible
information.

#### Agent-visible task

```text
Normalize non-empty names by stripping surrounding whitespace and
converting them to lowercase. Empty or whitespace-only names should
return None. Preserve all other behavior.
```

#### Agent-visible repository context

```text
src/sample/normalization.py

def normalize_name(value: str) -> str | None:
    normalized = value.strip()
    if not normalized:
        return None
    return normalized
```

#### Agent-visible tool names

```text
read_file
search_text
replace_text
run_check
```

The same benchmark case also contains evaluator-only information.

#### Hidden behavioral assertions

```text
normalize_name(" Alice ") == "alice"
normalize_name(" BOB ") == "bob"
normalize_name("   ") is None
```

#### Hidden regression assertions

```text
stable_identifier("Alice") == "user:Alice"
stable_identifier("BOB") == "user:BOB"
```

#### Hidden expected changed files

```text
src/sample/normalization.py
```

#### Hidden expected patch marker

```text
return normalized.lower()
```

#### Hidden scoring metadata

```text
primary_success = task_passes AND regression_passes
```

### Benchmark representation

The deterministic evaluator must represent the benchmark using two
separate structures:

```text
AgentVisibleCase
EvaluatorOnlyCase
```

`AgentVisibleCase` may contain only:

- task request;
- repository context;
- tool names.

`EvaluatorOnlyCase` may contain:

- behavioral assertions;
- regression assertions;
- expected changed files;
- expected patch markers;
- scoring metadata.

The agent payload builder accepts only `AgentVisibleCase`.

It must not accept `EvaluatorOnlyCase`.

### Frozen conditions

Four deterministic assembly conditions are evaluated.

#### A — clean assembly

The payload is constructed only from `AgentVisibleCase`.

Expected:

```text
payload constructed = true
hidden markers exposed = false
integrity passes = true
```

#### B — direct hidden-oracle contamination

A hidden behavioral assertion is deliberately appended to the
agent-visible repository context before the integrity check.

Contamination marker:

```text
normalize_name(" Alice ") == "alice"
```

Expected:

```text
payload constructed = true
hidden markers exposed = true
integrity passes = false
```

#### C — expected-patch contamination

The hidden expected patch marker is deliberately appended to the
agent-visible task request before the integrity check.

Contamination marker:

```text
return normalized.lower()
```

Expected:

```text
payload constructed = true
hidden markers exposed = true
integrity passes = false
```

#### D — metadata contamination

The hidden scoring rule is deliberately appended to the agent-visible
context before the integrity check.

Contamination marker:

```text
primary_success = task_passes AND regression_passes
```

Expected:

```text
payload constructed = true
hidden markers exposed = true
integrity passes = false
```

### Contamination detection

The experiment uses exact frozen contamination markers derived from the
evaluator-only record.

For each assembled agent payload, the integrity checker searches for
those evaluator-only markers.

The detector is deliberately narrow.

It tests accidental direct exposure of benchmark-owned hidden
information.

It is not a semantic leakage detector.

### Hidden marker set

The frozen hidden marker set contains:

```text
normalize_name(" Alice ") == "alice"
normalize_name(" BOB ") == "bob"
normalize_name("   ") is None
stable_identifier("Alice") == "user:Alice"
stable_identifier("BOB") == "user:BOB"
src/sample/normalization.py::expected_changed_file
return normalized.lower()
primary_success = task_passes AND regression_passes
```

The expected-changed-file marker is namespaced rather than checking the
raw file path because the file path legitimately appears in
agent-visible repository context.

This prevents the integrity checker from treating legitimate repository
knowledge as contamination merely because the evaluator also expects
that file to change.

### Integrity classification

For this experiment:

```text
integrity_passes = NOT hidden_markers_exposed
```

Behavioral correctness is not evaluated in 011E.

011E tests benchmark-input integrity only.

### Expected matrix

| Condition | Payload constructed | Hidden markers exposed | Integrity passes |
|---|---:|---:|---:|
| A — clean | true | false | true |
| B — hidden oracle | true | true | false |
| C — expected patch | true | true | false |
| D — scoring metadata | true | true | false |

### Expected aggregate

```text
expected matrix matched: 4/4
clean payloads: 1/4
contaminated payloads detected: 3/3
false contamination detections on clean payload: 0
```

### Success criterion

011E succeeds as an evaluation-methodology experiment if:

1. the clean payload contains no frozen evaluator-only markers;
2. all three deliberately contaminated payloads are detected;
3. the clean payload is not falsely rejected;
4. expected changed-file information is namespaced so that a legitimate
   repository path does not itself count as contamination;
5. the agent payload builder operates only on the agent-visible
   representation;
6. evaluator-only data remains available separately for post-run
   scoring;
7. all four observed classifications match the frozen matrix.

### Interpretation constraints

Passing 011E does not prove that a benchmark is free from every form of
contamination.

The detector recognizes exact benchmark-owned markers. It does not
detect paraphrases, semantic hints, information memorized during model
training, or leakage through external systems.

The experiment also does not establish that hidden tests are inherently
better than visible tests. Visible tests can be legitimate repository
evidence.

The relevant distinction is whether information was intentionally
classified as evaluator-only for a particular benchmark and then
accidentally exposed to the evaluated agent.

Expected changed files require particular care. A file path can be both
legitimate repository evidence and evaluator metadata. Therefore raw
string overlap alone is not sufficient to classify that path as leaked.

### Design implication

Hewn Bench should keep benchmark construction and benchmark execution
separate.

A benchmark case should conceptually contain:

```text
BenchmarkCase
├── agent_visible
│   ├── task
│   ├── repository/context
│   └── allowed tool interface
└── evaluator_only
    ├── task oracle
    ├── regression oracle
    ├── structural oracle
    ├── expected-change metadata
    └── scoring metadata
```

Only the `agent_visible` branch may participate in agent-input
construction.

The `evaluator_only` branch is consumed after execution for scoring and
diagnostics.

### Frozen implementation rule

After this design is committed, the agent-visible fields,
evaluator-only fields, hidden marker set, four conditions, expected
matrix, and integrity rule must not be changed in response to evaluator
output.

If the evaluator implementation contains a defect, preserve the
affected run, document the defect, correct only the evaluator, and
execute a new run.

## 011F — Hewn Bench synthesis

### Research question

What minimum production evaluation contract is justified by the evidence
from 011A–011E?

### Purpose

011F synthesizes the evaluation rules established by Module 11 into a
reusable production benchmark representation.

011F does not introduce a new empirical comparison.

Its purpose is to convert validated evaluation methodology into the
minimum `hewn.bench` API needed by later modules.

### Evidence being synthesized

#### 011A — Metric disagreement

011A demonstrated that protocol correctness, edit application, task
correctness, regression correctness, and behavioral success can disagree.

Therefore these measurements must remain separate.

#### 011B — Repeated-run stability

011B showed that repeated runs can reveal stable failure modes even when
behavioral success never changes.

It also showed that protocol-valid runs can remain behaviorally
unsuccessful.

Therefore individual run records must be preserved and repeated runs
must not be collapsed prematurely into one result.

#### 011C — Regression-aware scoring

011C demonstrated a deliberately constructed false success under
task-only evaluation.

Therefore primary behavioral success requires both requested behavior
and required regression checks.

#### 011D — Efficiency accounting

011D established that correctness and resource consumption answer
different questions.

Therefore efficiency fields remain separate from behavioral success and
no universal weighted quality/cost score is introduced.

#### 011E — Benchmark integrity

011E established an explicit boundary between agent-visible and
evaluator-only benchmark information.

Therefore benchmark construction must preserve that separation and
validate assembled agent-visible payloads for direct benchmark-owned
hidden-marker exposure.

### Production principles

Hewn Bench follows these rules:

1. Behavioral correctness is primary.
2. Protocol correctness is diagnostic.
3. Mechanical correctness is diagnostic.
4. Task correctness and regression correctness remain separately visible.
5. Behavioral success requires task correctness and required regression
   correctness.
6. Structural requirements, when present, are also required for
   behavioral success.
7. Failures remain in the denominator.
8. Repeated runs remain individually inspectable.
9. Resource usage is reported separately from correctness.
10. No universal weighted quality/cost score is produced.
11. Agent-visible and evaluator-only benchmark information remain
    structurally separate.
12. Benchmark provenance is recorded.
13. Hidden benchmark information must not participate in agent-input
    construction.
14. Expected patches and expected changed files are diagnostic metadata,
    not model-visible hints.

### Minimum production package

011F introduces:

```text
src/hewn/bench/
    __init__.py
    models.py
    scoring.py
    integrity.py
    aggregation.py
```

No CLI is required in 011F.

No benchmark fixture loader is required in 011F.

No model runner is required in 011F.

Those can be added when later modules need them.

### Benchmark case representation

A benchmark case contains two explicitly separated branches.

```text
BenchmarkCase
├── agent_visible
└── evaluator_only
```

#### Agent-visible branch

The minimum representation contains:

```text
task_request
repository_context
tool_names
```

These fields may participate in agent-input construction.

#### Evaluator-only branch

The minimum representation contains:

```text
behavioral_oracle_id
regression_oracle_ids
structural_oracle_ids
expected_changed_files
expected_patch_markers
hidden_markers
```

Oracle IDs identify evaluator-owned checks.

011F does not serialize executable Python callables into benchmark
records.

### Benchmark provenance

Each benchmark case records:

```text
benchmark_name
benchmark_version
task_id
```

Each benchmark run records:

```text
hewn_commit
model_id
model_configuration
hardware_description
repetition
```

These fields are descriptive provenance.

011F does not attempt to discover Git state or hardware automatically.

The caller supplies them explicitly.

### Run measurements

Each run record contains separate fields for:

```text
protocol_valid
edit_applied
task_passes
regression_passes
structural_passes
behavioral_success
```

`structural_passes` is optional.

If no structural oracle is required:

```text
structural_passes = None
```

### Behavioral scoring rule

Primary behavioral success is derived rather than supplied independently.

Without a structural requirement:

```text
behavioral_success =
    task_passes
    AND regression_passes
```

With a structural requirement:

```text
behavioral_success =
    task_passes
    AND regression_passes
    AND structural_passes
```

Protocol validity and edit application do not participate in this
formula.

This is intentional.

For example, an externally applied candidate patch may be evaluated for
behavior even when it was not produced through Hewn's normal editing
protocol.

### Failure accounting

A run may include:

```text
terminal_status
error
```

Examples include:

```text
completed
protocol_failure
stagnation
limit
model_error
execution_error
```

A failed run remains a run record.

The aggregation layer must not silently remove failed or
protocol-invalid runs.

### Resource accounting

Each run may record:

```text
model_calls
tool_calls
execution_calls
context_chars
wall_time_seconds
```

These are raw resource measurements.

Token fields are not required in the initial production contract because
the current model abstraction does not expose uniform measured token
usage.

No character-to-token conversion is performed.

### Repeated-run aggregation

For a collection of runs, Hewn Bench reports at minimum:

```text
total_runs
behavioral_successes
protocol_valid_runs
runs_with_edits
terminal_status_counts
```

When resource measurements are available, it also reports their totals
and ranges.

Individual run records remain available.

Aggregation does not reinterpret repeated runs as statistically
independent samples from a universal population.

### Resource dominance

Resource dominance may be evaluated only between runs with the same
behavioral classification.

Run X resource-dominates run Y when X uses no more of every measured
resource and strictly less of at least one measured resource.

If behavioral classifications differ, the relation is undefined.

The API represents this as:

```text
None
```

rather than `False`.

### Integrity validation

The agent-input builder accepts only the agent-visible benchmark
representation.

The integrity checker compares the resulting payload against the frozen
hidden markers owned by the evaluator-only representation.

An integrity result records:

```text
passes
exposed_markers
```

The initial production checker detects exact direct exposure only.

It is not described as a semantic contamination detector.

### Expected changed files

Expected changed files remain evaluator-only metadata.

A repository path may legitimately be visible to the agent.

Therefore the raw path itself is not automatically treated as a hidden
marker.

If benchmark construction needs to detect direct leakage of
expected-file metadata, it must use an evaluator-specific namespaced
marker rather than treating ordinary repository path visibility as
contamination.

### Mechanical correctness

`edit_applied` remains a diagnostic field rather than part of primary
behavioral success.

011F does not define one universal mechanical-success formula because
different benchmark execution modes may apply candidates differently.

Later benchmark runners may add more detailed mechanical fields without
changing the behavioral scoring contract.

### No headline score

011F deliberately does not define:

```text
overall_score
quality_score
efficiency_score
quality_per_cost
```

The benchmark should expose the underlying measurements.

Any later summary statistic must be justified by a separate experiment
and must not replace the raw measurements.

### Tests required

Production tests must cover at least:

1. task + regression success produces behavioral success;
2. task success + regression failure does not;
3. structural failure prevents behavioral success when structural
   verification is required;
4. structural `None` does not prevent success when no structural
   requirement exists;
5. protocol failure does not alter the behavioral formula;
6. aggregation keeps failed runs in the denominator;
7. aggregation counts protocol-valid runs separately;
8. aggregation counts runs with edits separately;
9. resource dominance works within successful runs;
10. resource dominance works within unsuccessful runs;
11. resource dominance is undefined across correctness classes;
12. clean agent payload passes integrity validation;
13. hidden marker exposure fails integrity validation;
14. raw expected-file path visibility is not automatically contamination;
15. benchmark provenance remains attached to cases and runs.

### Validation requirement

Before Module 11 is concluded:

```text
ruff check
mypy
focused Hewn Bench tests
full pytest suite
git diff --check
```

must pass.

### Interpretation constraint

011F is a production synthesis of the measurement rules validated by
011A–011E.

Passing its tests will show that the implementation matches those rules.

It will not establish that Hewn Bench is a universal or complete coding
agent benchmark.

The benchmark task distribution, oracle quality, regression coverage,
hardware controls, model controls, and external-agent adapters remain
separate concerns.

### Production decision

Module 11 earns a small production benchmark core.

It does not yet earn:

- a public leaderboard;
- a universal coding-agent score;
- statistical significance machinery;
- automatic cloud-agent comparison;
- semantic contamination detection;
- automatic benchmark generation;
- model-specific token estimation.

Those features require evidence from later modules or the final
cross-agent evaluation.

### Frozen implementation rule

After this synthesis is committed, the production behavioral scoring
rule, correctness dimensions, integrity boundary, resource-dominance
semantics, and minimum provenance fields must not be changed merely to
make later benchmark results look better.

Any future change to these semantics must be documented as a benchmark
version change.