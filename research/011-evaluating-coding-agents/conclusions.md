# Module 11 Conclusions — Evaluating Coding Agents Properly

## Research question

How should Hewn measure coding-agent capability so that improvements in
behavioral correctness can be distinguished from protocol compliance,
mechanical reliability, regressions, and additional inference or tool
cost?

## Answer

Hewn should not evaluate a coding agent with one proxy metric or one
headline score.

The evidence from Module 11 supports a layered evaluation model in which
behavioral correctness is primary while protocol compliance, edit
mechanics, resource consumption, and other intermediate measurements
remain separately visible.

## 011A — Metrics can disagree

The deterministic metric-disagreement experiment produced all four
frozen cases correctly.

In the four-condition diagnostic:

- protocol validity produced two false successes relative to behavioral
  success;
- edit application produced two false successes;
- task-only correctness produced one false success.

This validates the need to keep intermediate measurements separate.

It does not estimate how frequently those disagreements occur in real
coding-agent workloads.

## 011B — Repeated failure is still information

Three frozen tasks were executed five times each with the same nominal
Qwen2.5-Coder-1.5B configuration.

Observed behavioral success was:

```text
0 / 15
```

while protocol-valid outcomes were:

```text
10 / 15
```

All five repetitions within each task produced the same behavioral
failure classification.

For these tasks and this configuration, the immediate observed failure
was at the model-to-agent action-selection boundary: the model finalized
rather than using the available editing tools.

Because no patches were produced, the experiment did not measure patch
variability.

The repeated observations demonstrate observational stability of these
failures, not proof of deterministic model behavior and not a general
estimate of model reliability.

## 011C — Task-only evaluation can produce false success

The deterministic regression experiment constructed a patch that
satisfied every task-local assertion while breaking unrelated existing
behavior.

Task-only scoring classified two of four conditions as successful.

Regression-aware behavioral scoring classified only one as successful.

The deliberately regressing patch was therefore a false success under
task-only evaluation.

This validates regression checking as part of primary behavioral
success.

It does not establish that a finite regression suite can detect every
possible regression.

## 011D — Correctness and efficiency are different dimensions

The efficiency-accounting experiment correctly preserved behavioral
classification independently from resource usage.

Within equal behavioral classes:

```text
A resource-dominated B
C resource-dominated D
```

Across different behavioral classes:

```text
C versus A: dominance undefined
```

This prevents a cheap failure from being interpreted as superior to a
more expensive successful solution.

No combined quality/cost score is justified by this experiment.

## 011E — Evaluation information needs an explicit boundary

The benchmark-integrity experiment detected all three deliberately
introduced direct leaks:

```text
3 / 3
```

and produced zero false contamination detections on the clean payload.

It also preserved legitimate visibility of a repository path that
happened to be evaluator expected-change metadata.

This validates explicit separation of agent-visible and evaluator-only
benchmark information.

The exact-marker detector does not establish protection against semantic
leakage, paraphrases, pretraining contamination, or external leakage.

## 011F — Production synthesis

The evidence from 011A–011E justified introducing a small production
`hewn.bench` core.

The production design preserves:

- explicit benchmark provenance;
- agent-visible versus evaluator-only information;
- protocol correctness;
- edit application;
- task correctness;
- regression correctness;
- optional structural correctness;
- derived behavioral success;
- terminal failures;
- repeated-run records;
- raw resource measurements;
- aggregation;
- exact hidden-marker integrity validation.

No universal headline score was introduced.

## Primary scoring rule

For a benchmark without structural requirements:

```text
behavioral_success =
    task_passes
    AND regression_passes
```

For a benchmark with structural requirements:

```text
behavioral_success =
    task_passes
    AND regression_passes
    AND structural_passes
```

Protocol validity and edit application remain explanatory measurements.

## Evaluation hierarchy

The resulting conceptual hierarchy is:

```text
1. Protocol correctness
   Did the model communicate through the required interface?

2. Mechanical correctness
   Was a proposed change successfully applied?

3. Task correctness
   Does the requested behavior work?

4. Regression correctness
   Did required existing behavior remain intact?

5. Structural correctness
   Were required structural constraints preserved?

6. Behavioral success
   Did the task succeed without detected required regressions
   or structural violations?

7. Efficiency
   What resources were consumed to obtain that outcome?
```

The hierarchy does not imply that the first five dimensions should be
combined numerically.

They diagnose different failure modes.

## Benchmark integrity rule

A benchmark should conceptually contain:

```text
BenchmarkCase
├── agent_visible
│   ├── task
│   ├── repository/context
│   └── tool interface
└── evaluator_only
    ├── behavioral oracle
    ├── regression oracles
    ├── structural oracles
    ├── expected-change metadata
    └── scoring/integrity metadata
```

Only the agent-visible branch participates in agent-input construction.

Evaluator-only information is used after execution.

## Efficiency rule

Correctness is evaluated first.

Efficiency is then reported as raw measurements such as:

```text
model calls
tool calls
execution calls
context characters
wall time
```

Efficiency cannot convert failure into success.

Resource dominance is only defined within the same behavioral
classification.

## What Module 11 does not establish

Module 11 does not establish:

- that Hewn is competitive with frontier coding agents;
- that the current benchmark tasks represent real-world coding work;
- that five repetitions are sufficient for general reliability
  estimates;
- that hidden tests detect all regressions;
- that exact-marker integrity checks detect semantic contamination;
- that context characters accurately represent token cost;
- that all model calls have equal computational cost;
- that one benchmark score can represent coding-agent quality.

These remain later research problems.

## Production decision

Keep the `hewn.bench` core.

Do not add a universal score.

Do not optimize later modules against protocol compliance alone.

Do not discard failed runs.

Do not expose evaluator-only metadata to the agent.

Do not treat resource savings as capability improvements unless
behavioral correctness is reported alongside them.

## Design principle

> Measure whether the agent solved the problem first. Measure how it
> solved it second.

Module 11 therefore establishes the evaluation contract that later Hewn
experiments should use.

Future claims about local models, training, agent improvements, and
frontier-agent comparisons should be grounded in behavioral correctness,
regression checking, provenance, repeated observations, and explicit
resource accounting rather than proxy metrics alone.