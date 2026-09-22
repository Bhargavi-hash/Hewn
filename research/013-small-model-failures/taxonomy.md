# 013A — Historical Failure Taxonomy

## Research question

Where have small-model coding failures occurred in Hewn's existing experiments,
and how precisely can those failures be localized without assuming an
underlying cause that the experiments did not establish?

## Motivation

A failed coding-agent task does not establish that the model lacked general
reasoning capability.

Failure can occur at several boundaries:

- relevant evidence may not be available;
- available evidence may not be used correctly;
- task scope may be incomplete;
- the wrong action may be selected;
- an intended action may be represented incorrectly;
- a mechanically valid edit may be semantically wrong;
- deterministic feedback may be available but not successfully used;
- the model may stop before taking the required action.

Module 13 therefore begins with failure localization rather than capability
attribution.

## Principle

> A model failure is not automatically an agent failure.

A failure should first be classified by the observable boundary at which the
agent stopped making correct progress.

The classification does not automatically identify the cognitive or
architectural cause of the failure.

## Taxonomy

### 1. Input and evidence

#### `retrieval_failure`

The information required for the next correct decision was not present in the
model-visible evidence.

This category concerns evidence availability.

It should not be assigned when the required evidence was already available but
the model failed to use it correctly.

#### `evidence_utilization_failure`

Relevant evidence was available to the model, but the resulting decision or
output did not correctly incorporate that evidence.

This is intentionally narrower than calling the failure a reasoning failure.

The observation establishes that evidence availability alone was insufficient.
It does not establish why the model failed to use the evidence.

### 2. Reasoning and decision

#### `decomposition_failure`

The model's decomposition omitted, distorted, or incorrectly related required
parts of the task.

A plan can have correct file scope while still contain an incorrect semantic
operation.

#### `action_selection_failure`

The required action was available through the agent interface, but the model
selected a different action or finalized instead of taking it.

This category applies before evaluating whether a hypothetical edit would have
been correct.

#### `semantic_reasoning_failure`

The model had the relevant evidence and selected the appropriate class of
action, but the proposed semantics were incorrect.

This label requires stronger evidence than simple task failure.

It should be used only when earlier evidence and action-selection boundaries
have been sufficiently controlled.

### 3. Action generation

#### `protocol_failure`

The model failed to communicate through the required structured interface.

Examples include malformed JSON, fenced output when raw structured output was
required, truncation before a structured response completed, or another
response that the frozen parser cannot accept.

Protocol correctness is diagnostic. It is not equivalent to behavioral
correctness.

#### `edit_construction_failure`

The model selected an editing action but constructed a transformation that
could not validly represent or apply the intended change.

Examples include invalid anchors, conflicting replacements, malformed edits,
or incomplete multi-location transformations.

#### `grounding_failure`

The proposed action was insufficiently grounded in the actual current
repository state.

Examples can include references to text or repository structure that does not
exist in the state being edited.

Grounding failure is distinct from a semantically wrong edit that is
mechanically valid.

### 4. Feedback and recovery

#### `verification_interpretation_failure`

Execution or validation evidence was available, but the model interpreted that
evidence incorrectly.

This should not be assigned merely because verification reported failure.

The model must have been given the relevant feedback and then made an
incorrect decision about it.

#### `repair_failure`

A failure was detected and useful repair evidence was available, but the model
did not produce a successful repair within the frozen recovery policy.

This category does not imply that additional retries would necessarily fail.

### 5. Control

#### `stagnation`

The agent repeatedly failed to make meaningful progress despite remaining
within the control loop.

#### `premature_completion`

The model finalized while a required action remained undone.

This includes cases where an editing tool was available but the model returned
a final response without making the required repository change.

## Capability-boundary label

### `unresolved_capability_boundary`

This label is deliberately different from the observable failure categories.

It must not be assigned simply because a small model failed a task.

A candidate capability boundary requires evidence that the relevant external
support has already been supplied or controlled, including where applicable:

1. required repository evidence;
2. appropriate context;
3. deterministic structure or retrieval;
4. an available action representation;
5. deterministic validation;
6. execution feedback;
7. a reasonable recovery opportunity.

If behavioral failure persists after the relevant scaffolding has been
provided, the failure may become a candidate unresolved model-capability
boundary.

Even then, the result is scoped to the tested model, task distribution,
configuration, and intervention.

## Failure localization pipeline

The working localization model for Module 13 is:

```text
task understanding
        ↓
evidence acquisition
        ↓
evidence utilization
        ↓
scope / decomposition
        ↓
action selection
        ↓
edit construction
        ↓
edit grounding / applicability
        ↓
behavioral correctness
        ↓
verification interpretation
        ↓
recovery
        ↓
completion decision
```

This is a diagnostic ordering, not a claim that every task executes these
stages explicitly or exactly once.

A later-stage failure should not be used to infer that all earlier stages were
correct unless the experiment actually measured them.

## Classification rules

1. Classify the earliest observable boundary supported by the experiment.
2. Do not infer hidden reasoning processes from task failure alone.
3. Prefer `unknown` over an unsupported causal attribution.
4. Preserve multiple observations when an experiment exposes multiple distinct
   boundaries.
5. Protocol success does not imply behavioral success.
6. Mechanical edit success does not imply semantic correctness.
7. Correct scope does not imply correct implementation.
8. Detection of failure does not imply successful recovery.
9. Deterministic information should not be credited to model reasoning when
   Hewn already possesses that information mechanically.
10. Do not assign `unresolved_capability_boundary` during historical
    classification unless the historical experiment actually controlled the
    relevant preceding boundaries.

## Relationship to previous modules

Modules 1–12 progressively isolated different parts of the coding-agent
pipeline.

Repository intelligence and retrieval investigated evidence acquisition.

Context engineering investigated whether supplying stronger evidence was
sufficient for downstream behavior.

Editing experiments separated transformation representation and deterministic
applicability from semantic correctness.

Execution-feedback experiments separated failure detection from repair.

Planning experiments separated scope discovery and decomposition from correct
implementation.

Evaluation experiments separated protocol, mechanics, behavioral correctness,
regressions, and resource usage.

Module 13 uses those separations as diagnostic evidence rather than collapsing
all failures into a single model-accuracy number.

## 013A non-goals

013A does not:

- estimate the frequency of these failures in real-world coding tasks;
- claim that the categories are exhaustive;
- claim that categories correspond to independent cognitive mechanisms;
- determine that a larger model would solve a failure;
- introduce a new model intervention;
- run new inference;
- assign a universal capability limit to the 1.5B model.

The taxonomy exists to define what Module 13 will measure next.

## Decision

Use observable failure boundaries as the unit of diagnosis.

Do not use "small model failure" as a causal explanation.

The next experiment should test whether targeted system interventions can move
specific observed failures from behavioral failure to behavioral success.
---

# Post-experiment taxonomy note

The taxonomy above was frozen before the 013B and 013C intervention
experiments. The categories are intentionally preserved rather than rewritten
after observing those results.

The intervention experiments reinforced the need to classify failures at the
earliest observable boundary while preserving downstream observations.

In particular:

- 013B-1 exposed premature-completion and action-selection behavior.
- 013B-2 moved the observable boundary to edit construction and grounding.
- 013C exposed subsequent recovery and protocol-serialization failures after
  the mechanical edit failure had been explicitly identified.

These observations do not require a new failure category.

They demonstrate that one run can encounter multiple boundaries sequentially
and that an intervention can remove or move an earlier boundary without
producing behavioral success.

For future Hewn evaluation, failure records should therefore distinguish:

1. the earliest observed blocking boundary;
2. downstream failures exposed after an intervention;
3. whether the intervention changed observable behavior;
4. whether it produced an effective repository mutation; and
5. whether the final requested behavior became correct.

`unresolved_capability_boundary` remains reserved for cases where relevant
agent-side scaffolding has been controlled or provided and the remaining
failure cannot be assigned more specifically from observable evidence.
