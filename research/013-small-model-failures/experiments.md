# Module 13 Experiments — Why Small Models Fail

## 013B — Controlled Failure Interventions

### Research question

Can targeted deterministic agent mechanisms convert observed small-model
failure modes into behavioral success without changing the model?

### Experimental principle

A system intervention should target one observable failure boundary at a time.

The intervention must not provide evaluator-only information, expected patches,
hidden test results, or task-specific implementation instructions.

Behavioral correctness remains the primary outcome.

Intermediate improvements such as protocol validity, tool use, edit
application, or additional model activity are diagnostic rather than success.

Resource cost must remain visible.

---

## 013B-1 — Premature completion

### Historical observation

Module 11 observed repeated tasks in which the model finalized instead of
using the available editing mechanism.

The immediate observable failure therefore occurred before patch generation at
the action-selection/completion boundary.

### Question

If Hewn can determine that a task requires repository mutation, can refusing
completion before any edit attempt improve behavioral success?

### Hypothesis

A deterministic completion requirement will increase edit attempts because a
final response before any edit attempt will no longer terminate the task.

This may improve behavioral success if premature completion was the blocking
failure.

It may instead expose a later failure boundary if the model begins editing but
produces an invalid or semantically incorrect transformation.

### Independent variable

Completion policy.

#### Baseline

The existing agent behavior is preserved.

A model-generated final response may terminate the run even when no edit has
been attempted.

#### Intervention

For a task explicitly marked as requiring repository mutation:

```text
if edit_attempts == 0:
    reject finalization
    provide bounded deterministic feedback
    allow one additional model action
```

The feedback communicates only:

```text
The task requires a repository modification, but no edit has been attempted.
Use an available repository-editing action before completing the task.
```

The feedback must not identify:

- the file to modify;
- the symbol to modify;
- the expected patch;
- hidden evaluator information;
- the semantic implementation required.

### Controls

Hold fixed:

- model artifact;
- quantization;
- inference runtime;
- temperature;
- model context configuration;
- repository fixture;
- task request;
- repository evidence;
- available tools;
- edit representation;
- behavioral evaluator;
- regression evaluator.

The intervention changes only completion acceptance and permits one bounded
additional action opportunity after rejected premature completion.

### Task set

Reuse the frozen Module 11 repeated-run tasks that exhibited premature
completion where practical.

Do not alter task wording after observing 013B-1 model outputs.

If compatibility changes are required to replay those tasks through the Module
13 harness, document them before running inference.

### Measurements

For every run record:

- protocol validity;
- model calls;
- tool calls;
- edit attempts;
- edit applications;
- task correctness;
- regression correctness;
- behavioral success;
- terminal reason;
- context size or characters where available;
- wall time where available.

### Primary outcome

Behavioral success.

### Diagnostic outcomes

Compare:

```text
premature completion rate
edit-attempt rate
edit-application rate
protocol-valid rate
terminal failure classification
```

An increase in edit attempts without an increase in behavioral success is not
a behavioral improvement.

Instead, it indicates that the intervention moved the observable failure to a
later boundary.

### Repetition policy

Use the same repetition count for baseline and intervention.

The initial experiment should remain small.

Do not expand the task set or retry budget after observing results unless a
separate follow-up experiment is frozen first.

### Success interpretation

If the intervention converts failures into behavioral successes, the result
supports moving this completion decision from model discretion into
deterministic agent control for tasks known to require mutation.

If premature completion decreases but behavioral success does not improve,
the intervention still provides diagnostic information: action selection was
one failure boundary, but another downstream boundary remains.

If the intervention does not reduce premature completion or edit-free
termination, inspect the control implementation before making a model
capability claim.

### Non-claims

013B-1 does not establish:

- that every coding task requires mutation;
- that Hewn can infer mutation requirements for arbitrary natural-language
  requests;
- that forcing tool use improves semantic reasoning;
- that additional model calls are free;
- that the tested model has reached an intrinsic capability limit;
- that the result generalizes beyond the frozen tasks and configuration.

### Decision rule

The deterministic completion policy earns consideration for production only
if it prevents the targeted failure without introducing unacceptable
behavioral regressions or uncontrolled looping.

The intervention must remain bounded.

### Design principle

> Do not ask the model to decide something the agent can establish
> mechanically.

When completion is mechanically impossible because a required repository
mutation has not occurred, Hewn should treat that as agent state rather than
model judgment.

## 013B-1 design clarification after implementation inspection

Inspection of the production agent loop revealed that the historical Module 11
baseline already rejected premature finalization under
`CompletionRequirement.VERIFIED`.

A final response with verification state `UNKNOWN` was rejected with feedback
that successful verification had not yet been observed. Repeated rejected
finalizations could then terminate through stagnation.

Therefore 013B-1 is not a comparison between:

```text
completion allowed
vs
completion rejected
```

The historical baseline already implemented completion rejection.

The controlled comparison is instead:

```text
generic verification-state rejection
vs
boundary-specific mutation-state rejection
```

For frozen mutation tasks, the intervention communicates that no repository
edit has yet been attempted before communicating the ordinary verification
requirement.

The intervention still does not reveal:

- which file should change;
- which symbol should change;
- what replacement should be made;
- expected patch contents;
- evaluator-only information.

### Revised hypothesis

Boundary-specific deterministic feedback may improve action selection relative
to generic completion rejection when the observable blocking state is known
mechanically.

If the model begins attempting edits but behavioral success remains zero, the
intervention has moved the observable failure boundary without solving the
downstream implementation problem.

### Implementation constraint

013B-1 must preserve the production `Agent.run()` control loop.

The experiment must not perform hidden model calls or implement a parallel
research-only agent loop.

The intervention should be represented as a completion policy used by the
existing agent control loop.