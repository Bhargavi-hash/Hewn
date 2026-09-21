# Module 11 — Evaluating Coding Agents Properly

## Central question

How should Hewn measure coding-agent capability so that improvements in
behavioral correctness can be distinguished from protocol compliance,
mechanical reliability, regressions, and additional inference or tool
cost?

## Motivation

Modules 1–10 produced multiple examples where intermediate metrics and
actual coding success disagreed.

Examples include:

- valid model protocol without correct repository behavior;
- successful edit application without correct behavior;
- high retrieval recall without successful implementation;
- planning improvements in file selection without improved behavioral
  success;
- reviewer signals that duplicated deterministic execution evidence;
- additional context without demonstrated behavioral benefit;
- repeated repository retrieval without demonstrated active discovery
  cost.

These results show that no single proxy metric is sufficient for
evaluating a coding agent.

Module 11 develops a benchmark methodology before Hewn begins its
model-focused work.

## Primary hypothesis

Behavioral correctness with regression checking should be the primary
measure of coding-agent success.

Protocol validity, retrieval quality, edit validity, tool use, context
size, latency, and compute should be reported as explanatory or
efficiency measurements rather than substitutes for behavioral success.

## Secondary hypotheses

1. Proxy metrics can improve while behavioral success remains unchanged.

2. Task-local verification can report success while unrelated repository
   behavior regresses.

3. Repeated runs are required to distinguish stable capability from
   run-specific outcomes.

4. Additional model calls, context, tool calls, execution, latency, and
   compute are costs and should be reported alongside quality.

5. Hidden evaluation information must remain unavailable to the agent.

6. Benchmark tasks must have explicit behavioral oracles rather than
   relying on model self-assessment.

7. Failed and protocol-invalid runs must remain part of aggregate
   reporting.

## Evaluation layers

Hewn Bench should distinguish at least five layers.

### 1. Protocol correctness

Did the model produce a response Hewn could parse and execute?

Examples:

- protocol validity;
- schema validity;
- tool argument validity.

### 2. Mechanical correctness

Could Hewn mechanically perform the proposed action?

Examples:

- edit preflight success;
- edit application success;
- authorized tool execution;
- command completion.

### 3. Task correctness

Did the requested behavior become correct?

This must be determined by an evaluator outside the model.

### 4. Regression correctness

Did behavior outside the immediate task remain correct?

A task is not fully successful merely because its targeted check passes.

### 5. Efficiency

What resources were required?

Examples:

- model calls;
- tool calls;
- discovery operations;
- context characters or tokens;
- generated tokens where measurable;
- execution calls;
- wall time;
- retries;
- human intervention;
- compute or monetary cost where measurable.

## Primary success definition

For a coding task, the primary completion outcome is:

    requested behavior passes
    AND
    required regression checks pass

Protocol validity or edit application alone does not constitute task
success.

## Experimental rules

### Freeze before execution

Task definitions, expected behavior, evaluator logic, conditions, and
primary metrics must be frozen before observing model output.

### Preserve failures

Protocol failures, timeouts, rejected edits, incorrect final responses,
and regressions remain in the denominator.

### Separate agent-visible and evaluator-only information

Hidden expected files, behavioral oracles, mutation labels, and scoring
logic must never enter model context.

### Do not repair benchmark tasks after observing model behavior

A fixture may be corrected only for a genuine benchmark defect.

Such corrections must be documented and require a new benchmark version
when they can affect results.

### Report denominators

Measurements must include their sample counts.

Avoid claims such as "3x better" from tiny diagnostic samples.

### Distinguish diagnostics from estimates

Small single-run experiments may identify mechanisms.

They must not be presented as stable estimates of coding-agent
performance.

## Proposed experiments

### 011A — Metric disagreement

Construct tasks that distinguish:

- protocol-valid but behaviorally wrong;
- mechanically valid but behaviorally wrong;
- task-correct but regression-producing;
- fully correct.

Measure how often proxy metrics disagree with the primary behavioral
outcome.

### 011B — Repeated-run stability

Repeat a frozen task set under nominally identical conditions.

Measure:

- behavioral success distribution;
- protocol validity;
- tool use;
- patch variation;
- latency variation.

Determine how much confidence should be placed in one-run diagnostics.

### 011C — Regression-aware scoring

Compare:

- targeted task verification;
- targeted plus impacted verification;
- full verification.

Measure false success when only the targeted behavior is considered.

### 011D — Efficiency accounting

For the same task outcomes, record:

- model calls;
- tool calls;
- context;
- execution;
- retries;
- wall time;
- compute where available.

Do not combine quality and cost into a single score unless a later
experiment demonstrates that such an aggregation is useful.

### 011E — Benchmark integrity

Test evaluator boundaries explicitly.

Verify that:

- hidden oracles are not model-visible;
- expected patches are not model-visible;
- task metadata does not reveal answers;
- fixture state is reset between runs;
- one run cannot contaminate another;
- failed runs remain recorded.

### 011F — Hewn Bench

Use the experimental results to freeze a reusable benchmark result
schema and runner.

The benchmark should preserve raw per-run measurements and compute
aggregate summaries separately.

## Intended production output

Module 11 may promote evaluation infrastructure into Hewn because
evaluation is required independently of whether any individual agent
feature improves performance.

Potential production components include:

    hewn.bench
        BenchmarkTask
        BenchmarkRun
        BenchmarkResult
        VerificationResult
        CostMetrics
        aggregate_results(...)

Exact production APIs are not frozen yet.

They should be earned from 011A–011E rather than designed entirely in
advance.

## Non-goals

Module 11 does not attempt to:

- prove Hewn is better than another coding agent;
- optimize Hewn against the benchmark;
- compare against Codex or Claude Code;
- train a model;
- create a universal coding benchmark;
- reduce quality and cost to one headline score.

Cross-agent comparison belongs to Module 17.

## Scientific standard

Every future Hewn performance claim should be traceable to:

- benchmark version;
- Hewn commit;
- model and model configuration;
- hardware where relevant;
- task set;
- number of runs;
- evaluator definition;
- raw per-run results;
- aggregate calculation.

The benchmark should make it harder to accidentally produce a flattering
result.

## Desired outcome

Module 11 succeeds if it produces an evaluation protocol capable of
telling the difference between:

- a model that speaks the protocol correctly;
- an agent that edits successfully;
- an agent that solves the requested task;
- an agent that solves it without regressions;
- an agent that does so efficiently.

The purpose of Hewn Bench is not to make Hewn look good.

It is to make incorrect claims about Hewn difficult.