# Module 8 — Planning and Subagents

## Central question

Does explicit task decomposition improve a small coding model's ability to
complete multi-step repository changes enough to justify the additional
inference and coordination cost?

## Motivation

Modules 1–7 progressively separated coding-agent capability into control,
tools, repository structure, retrieval, context construction, editing, and
execution feedback.

Those experiments also exposed a recurring limitation: a small model may have
access to sufficient evidence and safe tools while still failing to coordinate
multiple required decisions into a correct repository change.

Module 8 investigates whether decomposition can reduce that reasoning burden.

The goal is not to demonstrate that a multi-agent architecture is inherently
better. Planning and subagents introduce additional inference, latency,
context transfer, failure modes, and coordination complexity. They should be
added to Hewn only when controlled experiments show that they improve useful
behavior enough to justify those costs.

## Primary hypothesis

For multi-step repository tasks, explicit structured planning will improve
identification and coordination of required changes, and useful plans will
increase downstream behavioral implementation success relative to direct
implementation.

## Competing hypotheses

1. A small model may already perform the necessary planning implicitly, making
   a separate planning call redundant.

2. A weak planner may anchor the implementer to incorrect files or operations
   and reduce downstream performance.

3. Planning may improve intermediate plan-quality metrics without improving
   executable task success.

4. Deterministic repository grounding may provide more useful decomposition
   support than additional unconstrained model reasoning.

5. Independent review may detect failures missed by an implementation
   trajectory, but detection does not imply successful repair.

## Scope

Module 8 studies:

- explicit task decomposition;
- structured plans;
- plan quality;
- plan-conditioned implementation;
- deterministic grounding for planning;
- independent review;
- coordination costs;
- planner/implementer/reviewer boundaries.

Module 8 does not study:

- persistent repository memory;
- agent security;
- model training;
- fine-tuning;
- large-scale benchmark reliability;
- general multi-agent collaboration;
- autonomous arbitrary shell execution.

Persistent repository intelligence belongs to Module 10.
Large-scale evaluation belongs to Module 11.
Model specialization belongs to Modules 12–15.

## Architectural principle

A new model call must earn its place.

Hewn should prefer deterministic computation when repository facts can be
recovered mechanically and use model inference for decisions that require
semantic reasoning.

Therefore this module compares decomposition strategies rather than assuming
that more agents produce more intelligence.

## Experimental sequence

### Experiment 008A — Planning quality

Measure whether structured planning identifies the required repository scope
for frozen multi-step tasks.

Compare model planning with and without deterministic repository grounding.

No edits are applied.

### Experiment 008B — Plan-conditioned implementation

Compare direct implementation against implementation conditioned on frozen
plans from 008A.

The primary outcome is behavioral task success, not plan appearance.

### Experiment 008C — Independent review

Measure whether a fresh reviewer can identify incorrect implementations using
the task, resulting code or diff, and deterministic verification evidence.

Reviewer detection and reviewer repair are measured separately.

### Experiment 008D — Full orchestration

Only if earlier experiments justify it, evaluate a composed
planner → implementer → verifier → reviewer workflow against the simpler agent
trajectory.

## Initial task distribution

Use eight frozen repository tasks:

- two same-file multi-operation tasks;
- two cross-file dependency tasks;
- two behavior plus verification/configuration tasks;
- two repository-navigation/dependency-reasoning tasks.

Tasks must require genuine coordination rather than a single obvious textual
replacement.

The fixture set must be frozen before the first measured model call.

## Planning output

Plans must use a strict structured schema.

At minimum a plan identifies:

- affected files;
- affected symbols where applicable;
- required operations;
- verification targets.

The planner does not edit files.

## Plan-quality measurements

Measure mechanically where possible:

- protocol validity;
- required-file recall;
- unnecessary-file count;
- required-symbol recall;
- verification-target recall;
- plan size;
- model-call latency.

Natural-language operation quality must not be converted into a quantitative
score unless a deterministic scoring representation is defined before the
experiment.

## Implementation measurements

For later implementation experiments measure:

- behavioral success;
- verification outcome;
- protocol validity;
- edit preflight success;
- files changed;
- unnecessary files changed;
- diff size;
- model calls;
- model-visible context;
- wall time;
- repair iterations;
- regressions.

## Controls

Unless an experiment explicitly changes one of these variables, hold constant:

- Qwen2.5-Coder-1.5B-Instruct Q4_K_M;
- llama.cpp serving configuration;
- temperature 0;
- context window 4096;
- maximum output budget;
- task wording;
- repository state;
- editing representation;
- deterministic validation;
- verification oracle;
- number of allowed implementation attempts.

Any unavoidable change is recorded as a confound.

## Interpretation constraints

Single temperature-zero runs are diagnostic observations, not estimates of
general model performance.

Planning quality and implementation success are separate outcomes.

A plan is not useful merely because it looks reasonable.

A reviewer detecting a problem is not equivalent to repairing it.

Additional model calls are costs and must be reported.

No experiment may be redesigned around observed model failures after the
fixture or condition has been frozen.

Failed and negative experiments remain part of the research record.

No claim about frontier-agent equivalence or superiority is made in this
module.
