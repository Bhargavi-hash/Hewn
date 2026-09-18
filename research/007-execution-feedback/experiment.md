# Module 7 Experimental Plan

## Experimental objective

Measure whether the representation of deterministic execution feedback
changes the ability of a small coding model to repair an already-applied
incorrect change.

The module must distinguish:

1. whether execution detected a problem,
2. whether the relevant evidence was exposed to the model,
3. whether the model understood the evidence,
4. whether the model proposed an applicable repair,
5. whether the repair corrected behavior,
6. whether the repair introduced regressions.

## Core experimental unit

A task begins from a repository state containing an intentionally incorrect
implementation.

The incorrect implementation must already be syntactically applicable.

This avoids conflating execution-feedback research with Module 6 editing
application failures.

For each task:

1. copy the frozen fixture into an isolated temporary workspace,
2. run the designated verification command,
3. capture deterministic execution evidence,
4. present a controlled representation of that evidence to the model,
5. request one complete atomic edit batch,
6. validate the proposed batch,
7. commit it only if the complete batch passes preflight,
8. independently rerun verification,
9. measure behavioral correctness and regressions.

Unless an experiment explicitly studies iterative repair, each task receives
one repair proposal.

## Initial feedback conditions

### Condition A — Failure signal only

The model receives only:

- the original task,
- relevant source,
- the fact that verification failed.

It does not receive the failure details.

Purpose:

Establish whether merely knowing that the current implementation is wrong is
sufficient to trigger a useful repair.

### Condition B — Raw execution output

The model receives:

- the original task,
- relevant source,
- raw stdout and stderr from the failed verification command.

Purpose:

Measure repair behavior when the model must interpret the execution tool's
native output.

### Condition C — Normalized execution evidence

The model receives:

- the original task,
- relevant source,
- a deterministic structured summary of the failure.

The normalizer may extract mechanically available fields such as:

- verification tool,
- failing test or check,
- exception type,
- exception message,
- assertion expected value where mechanically recoverable,
- assertion actual value where mechanically recoverable,
- source location,
- concise traceback location.

The normalizer must not infer the intended repair.

Purpose:

Test whether Hewn can reduce feedback context while preserving useful
execution signal.

## Later conditions

Only add these after Conditions A-C are measured.

### Context-enriched normalized evidence

Add the smallest source region mechanically associated with the failure.

### Targeted verification

Compare a smaller impacted check with the full verification suite.

### Iterative execution repair

Allow another verification-and-repair cycle only after the value of the
feedback representation itself has been established.

Do not begin with an open-ended repair loop.

## Controls

Hold constant where possible:

- model,
- quantization,
- temperature,
- context window,
- maximum output tokens,
- task wording,
- supplied source,
- editing representation,
- batch preflight rules,
- verification command,
- fixture state,
- number of repair proposals.

If a configuration change is structurally required, record it explicitly as
a confound.

## Model configuration

Initial model:

- Qwen2.5-Coder-1.5B-Instruct Q4_K_M
- llama.cpp
- temperature 0
- context window 4096

Output-token limits must be frozen before the first measured comparison.

## Editing representation

Use the Module 6 candidate representation:

- one structured atomic batch,
- exact replacements underneath,
- deterministic preflight,
- no missing anchors,
- no ambiguous anchors,
- no no-op replacements,
- all-or-nothing commit.

Do not introduce another editing primitive during the initial feedback
comparison.

## Fixture dimensions

The primary Module 7 fixtures should vary execution-feedback shape rather
than editing shape.

Include tasks representing at least:

1. assertion-value mismatch,
2. runtime exception,
3. Boolean/branch semantic error,
4. incomplete multi-location behavior,
5. type-check failure,
6. lint/static-analysis failure.

Fixtures must be frozen before model evaluation.

Module 6 fixtures may be retained as continuity probes but should not define
the entire Module 7 benchmark.

## Metrics

Record per task:

- feedback condition,
- feedback characters,
- feedback lines,
- model calls,
- model latency,
- protocol success,
- proposed edit count,
- preflight success,
- files modified,
- lines added,
- lines deleted,
- syntax validity,
- verification result before repair,
- verification result after repair,
- behavioral success,
- regression status,
- final diff.

Where available, also record:

- failing-check count,
- normalized evidence size,
- raw evidence size,
- feedback compression ratio.

## Outcome taxonomy

### protocol_failure

The model response cannot enter the editing system.

### application_failure

The proposed repair cannot pass deterministic edit preflight.

### invalid_code

The repair applies but produces syntactically invalid code.

### verification_failure

The repair applies and remains syntactically valid but verification still
fails.

### regression

The targeted failure is corrected but another previously passing check
fails.

### success_with_extra_changes

Verification passes, but the repair modifies files outside the expected
source set.

### success

The repair applies, required verification passes, tests remain unmodified,
and no unexpected files are changed.

## Interpretation constraints

Do not infer broad model capability from this small benchmark.

Do not describe a feedback representation as better solely because one run
has a higher success count.

Inspect individual failure traces.

Separate:

- detection quality,
- evidence representation,
- model reasoning,
- edit application,
- behavioral verification.

A normalized feedback condition succeeding where raw feedback fails is not
by itself proof that normalization generally improves small models.

Temperature zero does not make model execution perfectly deterministic.

Repeated trials and broader repositories belong in Module 11.

## Initial experiment sequence

### Experiment 001

Freeze and validate the execution-feedback fixtures.

No model evaluation.

### Experiment 002

Failure-signal-only repair baseline.

### Experiment 003

Raw execution-output repair.

### Experiment 004

Normalized execution-evidence repair.

### Experiment 005

Matched analysis of feedback size and repair behavior across Conditions A-C.

Only after Experiment 005 decide whether context enrichment, targeted
verification, or iterative repair is justified.