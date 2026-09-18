# Module 6 Results

Results are recorded after each frozen experiment.

No production editing policy is selected before the corresponding experiment is run.

## Experiment 001 — Initial `replace_text` end-to-end baseline

### Configuration

- Model: Qwen2.5-Coder-1.5B-Instruct Q4_K_M
- Temperature: 0
- Tasks: 6 frozen editing fixtures
- Relevant source supplied in the initial request
- Editing primitive: `replace_text`
- Completion requirement: `VERIFIED`
- Runs per task: 1
- Repeated trials: no

### Results

| Metric | Result |
|---|---:|
| Behavioral success | 0/6 |
| Agent finalized | 0/6 |
| Tasks with an edit attempt | 0/6 |
| Tasks with an applied edit | 0/6 |
| `replace_text` attempts | 0 |
| Protocol failures | 6/6 |

All six tasks terminated with `ModelProtocolError` before any
`replace_text` invocation. Therefore the editing primitive received
zero treatment exposure.

### Protocol diagnostic

A separate single-task diagnostic was performed on `edit-001` to
inspect the raw model response without changing the parser.

The model returned a semantically valid Hewn final-response object
wrapped in a Markdown JSON fence. The strict protocol parser rejected
the response because Hewn requires exactly one JSON object with no
surrounding Markdown.

The response also claimed that the repository had been modified even
though no editing tool had been invoked.

This reveals two distinct pre-editing failures:

1. protocol formatting: the model wrapped the JSON object in a
   Markdown fence;
2. action/completion grounding: the model attempted to finalize and
   claimed that the modification had occurred without performing an
   edit.

### Interpretation

Experiment 001 does not provide evidence for or against the reliability
of `replace_text`. No editing operation was attempted.

Relaxing the JSON parser would not by itself solve the observed
failure. Removing the Markdown fence would make the diagnostic response
parseable, but it would still be an unsupported finalization with no
repository modification.

The next experiment should isolate editing representation from
independent action selection and completion behavior by requiring the
model to propose an edit before verification.

## Experiment 002 — Controlled single-action `replace_text`

### Question

When action selection and completion are removed, can the model express
the required code modification through one exact-once `replace_text`
operation?

### Controls

- Model: Qwen2.5-Coder-1.5B-Instruct Q4_K_M
- Temperature: 0
- Maximum output tokens: 256
- Same six frozen editing fixtures
- Relevant source supplied
- Exactly one permitted action: `replace_text`
- Final response unavailable during edit proposal
- Strict Hewn model protocol
- No JSON repair or Markdown-fence stripping
- Real Hewn `ToolExecutor`
- Independent evaluator-side verification
- One run per task

### Results

| Metric | Result |
|---|---:|
| Strict protocol success | 6/6 |
| Tasks with edit attempt | 6/6 |
| Tasks with applied edit | 5/6 |
| Behavioral success | 2/6 |
| Application failures | 1/6 |
| Verification failures after application | 3/6 |

### Per-task observations

#### edit-001 — unique expression

The model selected the exact expression `return a - b` and replaced it
with `return a + b`.

The edit applied successfully and all tests passed.

#### edit-002 — repeated expression

The target value appeared in more than one location. Rather than
selecting the repeated token alone, the model included surrounding
control-flow context in the `old` argument, producing a unique target.

The edit applied successfully and all tests passed.

This demonstrates that repeated text does not necessarily require a
different editing primitive when sufficient unique context can be
included in the replacement anchor.

#### edit-003 — insertion

The task required adding validation that did not yet exist. The model
used the desired new conditional as the `old` replacement target even
though that text was absent from the repository.

`replace_text` rejected the operation with:

`Text to replace was not found`

No repository modification occurred.

This is a targeting failure associated with expressing insertion through
an exact-replacement interface.

#### edit-004 — conditional logic

The model successfully replaced:

`authenticated and owner`

with:

`authenticated or admin`

The operation applied exactly as requested, but the resulting semantics
were incorrect. It allowed unauthenticated administrators and regular
authenticated non-owners.

This is not an application failure of `replace_text`. The proposed
transformation itself was behaviorally incorrect.

#### edit-005 — multiple edits in one file

The model successfully updated the clamping logic from 0/3 to 2/5, but
did not update `MIN_RETRIES` and `MAX_RETRIES`.

The resulting implementation failed the constant-value test.

Because the experimental protocol permitted exactly one edit action,
this result does not establish that `replace_text` cannot solve the
task. It shows that one edit action was insufficient for the complete
multi-location modification.

#### edit-006 — multiple files

The model successfully renamed `DEFAULT_TIMEOUT` to `REQUEST_TIMEOUT`
in `config.py`, but the dependent import and reference in `client.py`
were unchanged.

Test collection then failed with an import error.

As with edit-005, this exposes a single-action cardinality limitation.
It does not yet establish a limitation of sequential exact replacement.

### Interpretation

The controlled action constraint removed the pre-editing failure seen
in Experiment 001: all six responses satisfied the strict protocol and
all six attempted `replace_text`.

However, successful application was not equivalent to behavioral
correctness. Five edits applied, while only two tasks passed
verification.

The failures separate into different layers:

- edit-003: targeting/application failure for an insertion-shaped task;
- edit-004: semantic reasoning failure despite successful application;
- edit-005: incomplete multi-location change within one file;
- edit-006: incomplete coordinated change across files.

The latter two tasks were constrained by the experiment's one-action
protocol. They therefore motivate testing sequential `replace_text`
before introducing a more expressive editing primitive.

### Decision

Retain `replace_text`.

Do not introduce a patch-based editor yet.

The next experiment will allow multiple sequential `replace_text`
operations with application feedback while keeping the task set, model,
temperature, source availability, parser strictness, and deterministic
editor fixed.