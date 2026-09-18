# Module 7 Results — Execution as Feedback

No measured experiments have been run yet.

The task fixtures, verification commands, model configuration, and feedback
conditions must be frozen before the first model evaluation.


## Pilot — Failure Signal Run 001

`results/failure-signal-run-001.json` is retained as a historical pilot
artifact but is excluded from measured comparisons.

During post-run inspection, `feedback-005` was found to be incompletely
frozen:

- `config.py` was missing,
- `test_client.py` was empty,
- pytest therefore collected no tests for that fixture,
- edit preflight consequently rejected the model's proposed `config.py`
  edit because the file did not exist.

The remaining pilot traces may be useful diagnostically, but the aggregate
4/6 result is not treated as the Module 7 failure-signal baseline.

The fixture was corrected and the complete six-task starting state was
validated before the next measured run.

## Experiment 003 — Raw Execution Output

### Setup

The raw-output condition changed only the model-visible execution feedback
relative to the valid failure-signal baseline.

Both conditions used:

- Qwen2.5-Coder-1.5B-Instruct Q4_K_M
- temperature 0
- 4096-token context window
- 512 maximum output tokens
- one model call per task
- the same six frozen fixtures
- the same task and source context
- the same atomic exact-replacement edit batch
- the same deterministic preflight
- pytest as the verification oracle

The failure-signal condition exposed only that verification had failed.
The raw-output condition additionally exposed raw pytest stdout/stderr.

### Aggregate result

| Metric | Failure signal | Raw output |
| --- | ---: | ---: |
| Behavioral success | 4/6 | 3/6 |
| Strict protocol success | 6/6 | 6/6 |
| Preflight success | 5/6 | 4/6 |
| Committed batches | 5/6 | 4/6 |

In this six-task diagnostic, exposing raw pytest output did not improve
aggregate behavioral repair success. Neither task that failed in the
failure-signal condition became behaviorally correct in the raw-output
condition.

This is a one-run diagnostic and does not establish that raw execution
feedback generally harms small coding models.

### Paired observations

`feedback-001` remained a behavioral success.

`feedback-002` remained an application failure. Raw execution output
contained the exact failing source expression, but the model still proposed
a single-quoted exact-replacement anchor while the source used double
quotes. The proposed replacement itself became more concise and
semantically plausible, but deterministic preflight correctly rejected the
nonexistent anchor.

`feedback-003` regressed from behavioral success to verification failure.
The failure-signal condition repaired boolean precedence with
`authenticated and (owner or admin)`. With raw output, the model proposed
`authenticated and owner or admin and not authenticated`, after which two
tests failed. This is a concrete paired regression in this run, but not
evidence of a general causal effect.

`feedback-004` remained behaviorally correct but patch quality improved.
The failure-signal condition inserted an early correct implementation while
leaving stale unreachable logic. The raw-output condition instead changed
the two incorrect return values in place, producing a smaller and cleaner
behavioral repair. This demonstrates that behavioral pass/fail alone does
not capture patch quality.

`feedback-005` changed from verification failure to application failure.
The raw-output proposal contained the desired local repair,
`return DEFAULT_TIMEOUT` to `return REQUEST_TIMEOUT`, but included
additional no-op or nonexistent edits. Atomic preflight rejected the entire
batch. This separates identifying a useful repair from producing a valid
atomic edit proposal.

`feedback-006` remained a behavioral success.

### Current interpretation

The first two measured conditions suggest that simply increasing the amount
of execution evidence is not sufficient to improve this small model.

Raw output can contain useful diagnostic information while also adding
irrelevant structure, duplicated source text, traceback formatting, test
framework noise, and multiple competing signals.

The next experiment tests whether a deterministic normalized representation
can preserve mechanically recoverable failure evidence while reducing that
context.

## Module 7 conclusions

Module 7 separated execution feedback into distinct subsystems rather than
treating "run the tests and let the model fix it" as a single capability.

In the frozen six-task repair diagnostic, deterministic execution reliably
identified behavioral failures, but additional model-visible failure evidence
did not monotonically improve repair success for Qwen2.5-Coder-1.5B. Failure
signal only, raw pytest output, and normalized pytest evidence produced 4/6,
3/6, and 2/6 behavioral successes respectively in single temperature-zero
runs. These results are diagnostic rather than estimates of general model
performance.

Deterministic normalization reduced pytest feedback from 5,410 to 2,609
characters across the six fixtures, a 51.8% reduction, while preserving
mechanically extracted failure information. The smaller representation did
not improve behavioral repair success in this run.

Conservative deterministic edit grounding recovered one of two previously
rejected normalized-feedback batches, increasing preflight acceptance from
4/6 to 5/6, but behavioral success remained 2/6. The recovered proposal then
failed syntactically because its replacement lost indentation, separating
target identification from replacement placement and semantic correctness.

One additional normalized execution-feedback repair iteration was attempted
for the two eligible failed-but-applied repairs. Both model responses followed
the edit-batch protocol, but neither produced an applicable repair, yielding
0/2 recoveries. One retained an undefined identifier already reported by
pytest and targeted nonexistent source; the other proposed a deterministic
no-op. This does not establish that iterative repair is generally ineffective.

A deterministic reverse-import selector was also evaluated as a candidate
targeted-verification mechanism. Across eight frozen production modules,
transitive selection ranged from 3/31 to 25/31 test files and found
potentially impacted tests beyond direct imports in seven of eight cases.
However, a subsequent frozen eight-mutation failure-recall experiment was
non-diagnostic: none of the eight syntactically valid semantic mutations was
detected by the complete existing test suite. Consequently, this module
provides evidence for structural test-scope reduction, but not for preserved
regression-detection recall.

The resulting architectural direction is therefore conservative: execution
is a reliable detector and verifier; deterministic normalization can reduce
feedback context; deterministic validation should reject ambiguous or invalid
repairs; and dependency-aware targeted tests may serve as fast intermediate
feedback. Targeted verification is not promoted as completion-grade evidence
without a future recall study against a mutation corpus for which the full
suite detects regressions.

More broadly, the experiments show that execution feedback, evidence
normalization, model diagnosis, repair formulation, edit grounding, edit
application, and final verification should remain separate components. A
failure in one should not be attributed automatically to another.