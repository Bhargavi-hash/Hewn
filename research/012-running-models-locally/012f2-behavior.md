# 012F-2 — Behavioral Effects of Quantization

## Research question

When model family, prompt, inference runtime, and decoding configuration
are held fixed, does quantization measurably change coding-relevant
model behavior?

## Motivation

012F-1 showed that quantization changes systems properties in
non-monotonic ways.

It did not measure capability.

Tokens per second, artifact size, process memory, and latency cannot be
used as proxies for coding correctness.

012F-2 therefore evaluates behavioral correctness separately.

## Independent variable

Quantization:

- Q3_K_M
- Q4_K_M
- Q5_K_M
- Q6_K
- Q8_0

Use the exact artifacts frozen in 012F-1.

## Controlled variables

Hold fixed:

- model family and parameter count;
- llama.cpp runtime commit;
- hardware;
- threads: 4;
- configured context: 8192;
- parallel slots: 1;
- prompt cache: disabled;
- temperature: 0;
- task prompts;
- evaluator;
- maximum generation length;
- repetition count.

## Experimental unit

One observation is:

quantization × task × repetition

Every quantization receives exactly the same task prompt.

No task or evaluator may be changed after model outputs have been
observed.

## Task suite

Use a small frozen suite of coding-relevant reasoning tasks.

The suite should exercise distinct capabilities rather than repeatedly
testing syntax generation.

Target 10 tasks across:

1. bug localization;
2. code behavior prediction;
3. API-contract reasoning;
4. edge-case identification;
5. test selection;
6. dependency reasoning;
7. patch reasoning;
8. error-diagnostic interpretation;
9. repository-structure reasoning;
10. structured tool/action selection.

Each task must have a deterministic evaluator or exact acceptance
criteria.

Avoid subjective answer-quality scoring.

## Repetitions

Use 3 repetitions per task per quantization.

Total:

5 quantizations × 10 tasks × 3 repetitions = 150 observations.

Temperature remains zero.

Repeated runs are retained because Module 11 showed that temperature
zero should not be assumed to imply identical agent behavior.

## Primary metric

Behavioral success.

A task succeeds only when its frozen behavioral oracle passes.

Failures remain in the denominator.

## Secondary diagnostics

Record separately:

- protocol validity;
- task correctness;
- output length;
- finish reason;
- prompt tokens;
- generated tokens;
- wall time.

Do not combine these into a weighted score.

## Analysis

For each quantization report:

- successes / 30 observations;
- success rate;
- successes by task;
- repeated-run disagreement by task;
- protocol failures;
- median generated tokens;
- median wall time.

Also report pairwise disagreements.

For each task/repetition pair, determine whether two quantizations
produce different behavioral outcomes.

This allows quantization sensitivity to be distinguished from tasks on
which every representation behaves identically.

## Decision rules

Do not claim that a quantization preserves capability merely because
its aggregate success count matches another quantization.

Inspect task-level and repetition-level disagreements.

Do not claim degradation from stylistic output differences.

Only frozen evaluator outcomes determine behavioral success.

Do not rank quantizations using systems performance.

Systems measurements from 012F-1 and behavioral measurements from
012F-2 remain separate dimensions.

## Threats to validity

This is a small diagnostic suite using:

- one model family;
- one parameter count;
- one runtime;
- one hardware platform;
- ten tasks;
- three repetitions.

It is not an estimate of general coding capability.

Temperature-zero repetitions may be correlated.

The experiment measures behavior under the frozen prompts and
evaluators only.

## Design principle

> Compression is only cheap when the behavior you need survives it.

## Staged execution rule

The experiment begins with one repetition of every task under every
quantization:

5 quantizations × 10 tasks = 50 observations.

After those 50 observations are complete, compare behavioral outcomes
for each task across quantizations.

If every task has the same behavioral classification under all five
quantizations, stop the experiment.

If at least one task has different behavioral classifications across
quantizations, run two additional repetitions for every task under
every quantization.

The escalation decision depends only on whether disagreement exists.
It must not depend on which quantization succeeds, which task
disagrees, or whether the result supports an expected ordering.

If escalated, the final experiment contains:

5 quantizations × 10 tasks × 3 repetitions = 150 observations.