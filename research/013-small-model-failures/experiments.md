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

### Bounded-intervention semantics

The phrase "allow one additional model action" refers to the scope of the
mutation-specific intervention, not to the total remaining lifetime of the
agent run.

The treatment behaves as follows:

1. Before any `replace_text` attempt, the first model-generated final response
   is rejected with the frozen mutation-specific feedback.
2. The next model response is the single additional action opportunity created
   by the intervention.
3. If that response is a `replace_text` attempt, whether successful or failed,
   the mutation-specific gate is satisfied and normal
   `CompletionRequirement.VERIFIED` behavior resumes.
4. If that response is another final response, the mutation-specific
   intervention is exhausted. Subsequent completion handling reverts to the
   ordinary VERIFIED completion policy and existing agent stagnation behavior.
5. The intervention does not alter `MAX_TURNS`, `max_stagnant_turns`, tool
   availability, verification semantics, or any other control-loop budget.

Therefore "bounded" means that mutation-specific feedback is injected at most
once per run. It does not mean that the experimental policy introduces a new
terminal condition after the additional action opportunity.

This interpretation preserves the production `Agent.run()` control loop and
changes only the information supplied at the targeted observable boundary.

### Bounded-intervention semantics

The phrase "allow one additional model action" refers to the scope of the
mutation-specific intervention, not to the total remaining lifetime of the
agent run.

The treatment behaves as follows:

1. Before any `replace_text` attempt, the first model-generated final response
   is rejected with the frozen mutation-specific feedback.
2. The next model response is the single additional action opportunity created
   by the intervention.
3. If that response is a `replace_text` attempt, whether successful or failed,
   the mutation-specific gate is satisfied and normal
   `CompletionRequirement.VERIFIED` behavior resumes.
4. If that response is another final response, the mutation-specific
   intervention is exhausted. Subsequent completion handling reverts to the
   ordinary VERIFIED completion policy and existing agent stagnation behavior.
5. The intervention does not alter `MAX_TURNS`, `max_stagnant_turns`, tool
   availability, verification semantics, or any other control-loop budget.

Therefore "bounded" means that mutation-specific feedback is injected at most
once per run. It does not mean that the experimental policy introduces a new
terminal condition after the additional action opportunity.

This interpretation preserves the production `Agent.run()` control loop and
changes only the information supplied at the targeted observable boundary.

### 013B-1 conclusion

013B-1 delivered mutation-specific completion feedback in 10/10 eligible runs but produced 0/10 subsequent edit attempts and 0/10 behavioral successes. The model instead reproduced controller feedback as subsequent final responses. Post-experiment implementation inspection identified a competing explanation: rejected final responses were not retained in conversational history, while controller rejection messages were represented as tool messages despite no corresponding tool call. Therefore the experiment establishes that the current feedback interface did not improve action selection, but does not isolate whether the failure is attributable to model capability or feedback representation.

## 013B-2 — Completion-feedback representation

### Motivation

013B-1 delivered mutation-specific completion feedback in all 10 eligible runs,
but produced zero edit attempts and zero behavioral successes.

Inspection after the frozen 013B-1 run identified a competing explanation.

For successful tool interactions, Hewn preserves conversational structure as:

assistant action
→
tool observation

For rejected final responses, however, the rejected assistant response is not
retained in model-visible conversation history. The completion rejection is
appended directly as a message with role `tool`.

The resulting history can therefore contain:

user task
→
tool completion rejection

without a corresponding assistant tool call.

In 013B-1, the model subsequently reproduced the controller feedback as its own
final response in all intervention-eligible runs.

This creates a feedback-interface confound. 013B-1 establishes that the current
feedback interface did not improve action selection, but it does not isolate
whether the failure arose from model capability or from the representation of
controller feedback.

### Research question

Does representing a rejected completion as coherent conversational history,
while preserving the same mutation-specific information, improve the model's
ability to select an editing action?

### Hypothesis

For mutation-required tasks, retaining the rejected assistant response and
representing the deterministic rejection as controller feedback through a
standard `user` message will increase edit attempts relative to the existing
completion-feedback representation.

Behavioral success remains the primary outcome.

An increase in edit attempts without an increase in behavioral success will be
interpreted only as movement of the observable failure boundary.

### Control

The control is the frozen 013B-1 treatment:

- rejected `FinalResponse` is not retained in conversation history;
- completion rejection is represented with role `tool`;
- mutation-specific feedback is delivered at most once;
- ordinary `CompletionRequirement.VERIFIED` behavior resumes afterward.

The frozen 013B-1 result is reused as the control observation.

### Treatment

When a `FinalResponse` is rejected:

1. retain the rejected model response as an `assistant` message;
2. append the deterministic completion rejection as a `user` message;
3. preserve the exact frozen mutation-specific feedback text from 013B-1;
4. preserve the existing completion policy, stagnation logic, turn budget,
   tools, task request, repository evidence, fixtures, and evaluators.

The controller message should be represented as:

`Controller feedback: <rejection reason>`

The semantic content of the rejection must not add file names, symbol names,
replacement text, expected patch information, evaluator-only information, or
other task-specific implementation guidance.

### Important interpretation constraint

013B-2 changes two aspects of the interface together:

- rejected assistant actions become visible in subsequent conversation history;
- completion rejection changes from an unmatched `tool` message to a standard
  `user` controller-feedback message.

Therefore a positive result would establish that the coherent feedback
interface improves downstream action selection, but would not separately
identify which of those two representation changes caused the improvement.

A later experiment may separate those factors if the distinction becomes
decision-relevant.

### Frozen tasks

Reuse the byte-equivalent 013B fixture set.

Intervention-eligible tasks:

- `stability-002`
- `stability-003`

`stability-001` remains an ineligible negative control.

No task wording or fixture content may be changed after treatment outputs are
observed.

### Controlled variables

Hold fixed:

- Qwen2.5-Coder-1.5B-Instruct;
- Q4_K_M quantization;
- llama.cpp runtime;
- temperature 0;
- context size 4096;
- maximum generation length;
- thread count;
- task requests;
- repository evidence;
- available tools;
- edit representation;
- completion requirement;
- maximum agent turns;
- stagnation threshold;
- mutation-specific feedback text;
- behavioral evaluators;
- regression evaluators;
- structural evaluators;
- repetition count.

### Repetitions

Use five repetitions per frozen task, matching 011B and 013B-1.

All frozen repetitions count.

Do not add retries or expand the task set after observing treatment results.

### Primary outcome

Behavioral success:

requested task behavior passes
AND
required regression checks pass
AND
required structural checks pass, when present.

### Diagnostic measurements

Record separately:

- protocol validity;
- intervention eligibility;
- intervention delivery;
- model calls;
- tool calls;
- edit attempts;
- successful edit applications;
- edit attempt after intervention;
- task success;
- regression success;
- structural success;
- behavioral success;
- terminal reason;
- changed files;
- patch hash;
- wall time.

### Interpretation

Possible outcomes include:

1. More edit attempts and more behavioral successes:
   the coherent feedback interface improved action selection and downstream
   task completion on the frozen tasks.

2. More edit attempts but unchanged behavioral success:
   the interface moved the observable failure boundary later, but did not solve
   downstream implementation correctness.

3. No increase in edit attempts:
   the 013B-1 failure cannot be explained solely by the tested coherent-feedback
   representation.

4. New protocol failures or regressions:
   the treatment introduced a new failure mode and should not be promoted.

No outcome from this experiment alone establishes an intrinsic capability limit
of the model.