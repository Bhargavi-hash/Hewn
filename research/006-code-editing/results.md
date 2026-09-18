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

## Experiment 003 — Sequential `replace_text` with application feedback

### Question

Can multiple sequential exact replacements plus application feedback
recover tasks that were incomplete or rejected under the single-action
condition?

### Configuration

- Model: Qwen2.5-Coder-1.5B-Instruct Q4_K_M
- Temperature: 0
- Maximum output tokens: 256
- Same six frozen editing fixtures
- Relevant source supplied initially
- Editing primitive: `replace_text`
- Maximum edit attempts: 4
- Application result returned after each attempt
- Updated relevant source returned after each attempt
- Explicit `done` control action
- Independent evaluator-side verification
- One run per task

### Results

| Metric | Result |
|---|---:|
| Behavioral success | 1/6 |
| Strict protocol success | 5/6 |
| Tasks returning `done` | 1/6 |
| Attempt-limit exhaustion | 4/6 |
| Total edit attempts | 19 |
| Successful applications | 8 |
| Rejected applications | 11 |

### Observed failure modes

#### Edit oscillation

On edit-001, the model made the correct change, reversed it on the next
turn, then restored the correct change before returning `done`.

On edit-004, the model alternated between two conditions for all four
allowed attempts. All four operations applied successfully, but the
final repository was identical to the initial repository.

This demonstrates that additional editing opportunities can introduce
edit churn when the model does not reliably recognize that an adequate
change has already been made.

#### Repeated rejected actions

On edit-002, the model proposed the same ambiguous no-op replacement on
all four attempts despite receiving an ambiguity rejection after each
attempt.

On edit-003, the model proposed the same nonexistent insertion target
on all four attempts despite receiving a not-found rejection.

Application feedback therefore did not produce recovery on these tasks
under this configuration.

#### Natural multi-edit response

On edit-005, the first model response contained two `replace_text`
objects followed by `done`.

The strict sequential protocol rejected the response because exactly
one JSON action was required per turn.

The response nevertheless provides evidence that the model represented
this multi-location task naturally as a set of edits rather than as a
single edit followed by a conversational continuation.

#### Cross-file targeting

On edit-006, the first replacement correctly renamed the declaration in
`config.py`. The model then attempted to update `client.py`, showing
awareness that another file required modification.

However, it selected the repeated identifier `DEFAULT_TIMEOUT` as the
exact replacement target on each remaining attempt. All three attempts
were rejected as ambiguous.

### Interpretation

The sequential-control configuration did not recover the multi-location
failures from Experiment 002 on this six-task run.

The traces show three important behaviors: oscillation after successful
edits, repetition after deterministic rejection, and difficulty deciding
when editing is complete.

Because Experiment 003 changed multiple factors relative to Experiment
002 — number of turns, application feedback, updated-source messages,
and an explicit completion decision — the difference in behavioral
success must not be attributed to sequential editing alone.

The edit-005 response also suggests a cleaner next experiment: allow the
model to express multiple exact replacements in one structured response
while removing the conversational control loop.

### Decision

Retain exact replacement as the underlying editing operation.

Do not promote the Experiment 003 conversational sequential loop.

Before introducing a patch-based editing primitive, test whether a
single structured batch of exact replacements can handle multi-location
tasks while preserving deterministic validation.

## Experiment 004 — Atomic batch of exact replacements

### Question

Can a small coding model express complete multi-location changes more
reliably as one structured batch of exact replacements than through a
single-edit or conversational sequential-edit protocol?

### Configuration

- Model: Qwen2.5-Coder-1.5B-Instruct Q4_K_M
- Temperature: 0
- Maximum output tokens: 512
- Same six frozen editing fixtures
- One model call per task
- Maximum six exact replacements per batch
- Relevant source supplied
- No conversational application feedback
- Atomic application
- Independent evaluator-side verification
- One run per task

The output-token limit differs from Experiments 002 and 003 because a
multi-edit batch can require a larger structured response. Therefore the
experiment is not a strict one-variable comparison with those runs.

### Results

| Metric | Result |
|---|---:|
| Behavioral success | 2/6 |
| Strict protocol success | 6/6 |
| Tasks producing an application attempt | 6/6 |
| Atomically applied batches | 5/6 |
| Total proposed edits | 9 |

Behaviorally correct tasks were edit-001 and edit-003.

### Observations

#### Unique localized edit

edit-001 passed, although the proposed replacement inserted a correct
return before the existing incorrect return rather than replacing the
incorrect expression directly.

The resulting function contained unreachable old code. The behavioral
test passed, but this demonstrates that behavioral success alone does
not imply a minimal or clean patch.

#### Repeated expression

edit-002 proposed two replacements. The second targeted
`return "pending"`, which occurred more than once.

Atomic preflight rejected the complete batch and left the repository
unchanged.

The first proposed edit also introduced a reference to `complete`,
which was not present in the supplied function. Therefore this task
contains both proposal-quality and exact-targeting problems.

#### Insertion

edit-003 passed.

The model used the existing function signature as a unique anchor and
replaced it with the same signature followed by the required validation
block.

This demonstrates that exact replacement was expressive enough to
represent insertion for this frozen task without a dedicated insertion
primitive.

#### Conditional reasoning

edit-004 produced and successfully applied:

`authenticated and owner or admin`

The resulting behavior incorrectly allowed an unauthenticated admin.

The observed failure was in the proposed condition rather than in edit
application. A more expressive text mutation primitive would not by
itself correct this proposal.

#### Multiple changes in one file

edit-005 correctly changed both retry constants using one exact
replacement but omitted the corresponding changes required inside
`normalize_retries`.

The batch applied successfully but failed behavioral verification.

The representation was capable of expressing additional edits; the
model did not propose the complete required transformation.

#### Multiple files

edit-006 proposed three replacements across two files.

It correctly renamed the declaration in `config.py` and the import in
`client.py`, but the third replacement was a no-op on the function
signature. The model failed to replace the remaining
`DEFAULT_TIMEOUT` reference in the function body.

The complete batch applied atomically, but verification failed with a
NameError caused by the stale reference.

This shows that the batch representation could carry a coordinated
cross-file edit set, while the proposed transformation remained
incomplete.

### Interpretation

The atomic batch representation achieved 2/6 behavioral success on
this six-task diagnostic, the same aggregate count as the controlled
single-action condition, but on a different task set.

Most importantly, the batch condition successfully represented the
previously failing insertion task and successfully carried multiple
coordinated replacements across files.

The remaining failures do not provide clear evidence that a more
expressive mutation primitive such as a general patch operation is
required. edit-004, edit-005, and edit-006 were successfully applicable
but semantically incomplete or incorrect proposals.

edit-002 remains an exact-targeting failure and is a candidate for
deterministic preflight feedback.

The run also exposed no-op proposals, suggesting that a future editing
validator should explicitly detect replacements where `old == new`.

### Decision

Do not introduce a general patch primitive yet.

Retain exact replacement as the underlying mutation operation and
retain atomic edit batches as a candidate higher-level representation.

Run one final Module 6 experiment testing whether deterministic
preflight errors can repair an invalid batch without introducing an
open-ended conversational editing loop.

## Experiment 005 — Deterministic preflight with one repair opportunity

### Question

Can deterministic preflight feedback help the small coding model repair an
otherwise unappliable atomic edit batch without introducing an open-ended
conversational editing loop?

### Configuration

- Model: Qwen2.5-Coder-1.5B-Instruct Q4_K_M
- Temperature: 0
- Maximum output tokens: 512
- Same six frozen editing fixtures
- One initial batch proposal per task
- Maximum six exact replacements per batch
- Relevant source supplied
- Atomic application
- Deterministic preflight before mutation
- Explicit rejection of no-op replacements
- Exactly one repair opportunity for invalid batches
- Valid batches receive no repair opportunity
- No compiler, test, or linter feedback to the model
- Independent evaluator-side behavioral verification
- One run per task

This experiment changes both the validation policy and the availability of
one repair call relative to Experiment 004. It should therefore be treated
as an evaluation of a candidate validation-and-repair design rather than a
strict single-variable causal comparison.

### Results

| Metric | Result |
|---|---:|
| Behavioral success | 2/6 |
| Initially valid batches | 4/6 |
| Repair attempts | 2/6 |
| Invalid batches repaired to valid | 0/2 |
| Committed batches | 4/6 |

Behaviorally correct tasks were edit-001 and edit-003.

### Invalid-batch repair behavior

#### edit-002 — ambiguous target

The initial batch failed deterministic preflight because an exact target
occurred more than once.

The model received the exact validation failure and one opportunity to
produce a complete replacement batch.

The repaired batch remained ambiguous and was rejected. No repository
changes were committed.

In this run, precise ambiguity feedback was insufficient for the model to
recover the target.

#### edit-006 — no-op proposal

The initial batch contained a replacement whose `old` and `new` text were
identical.

The stricter preflight validator rejected this as a no-op before mutation.

The model received the explicit no-op validation error and one repair
opportunity, but the repaired batch again contained a no-op and remained
invalid.

The validator therefore prevented a meaningless edit, but the repair
feedback did not produce a valid proposal in this run.

### Interpretation

Deterministic preflight improved the safety boundary by rejecting ambiguous
and no-op transformations before repository mutation.

However, neither of the two invalid initial batches was repaired to a valid
batch after one precise validation-feedback turn.

This six-task diagnostic therefore provides evidence for deterministic
preflight as a safety mechanism, but not for the claim that one preflight
repair turn reliably improves this model's editing ability.

Combined with the sequential-control behavior observed in Experiment 003,
the result does not justify adding a larger conversational editing loop
inside Module 6.

### Decision

Close the Module 6 editing-representation experiments.

Retain exact replacement as the underlying deterministic mutation
operation.

Promote atomic composition of exact replacements as the candidate
higher-level editing representation.

Retain deterministic preflight validation, including explicit rejection of
ambiguous, missing, and no-op replacements.

Do not introduce a general patch primitive based on the current evidence.

Do not add further model-visible execution feedback in Module 6. Compiler,
test, and linter feedback belong to Module 7.