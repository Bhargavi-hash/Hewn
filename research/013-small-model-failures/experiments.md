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

## Conclusions

013B-1 showed that mutation-specific completion feedback alone did not change action selection under the original feedback representation: all 10 eligible runs received the intervention, but none attempted an edit. Post-experiment inspection identified a representation confound because rejected assistant completions were omitted from history and controller feedback was represented as unmatched tool messages.

013B-2 changed only the completion-feedback representation while preserving the intervention information and other frozen controls. All 10 eligible runs subsequently attempted replace_text, compared with 0/10 in 013B-1, establishing that the tested coherent representation changed observable action selection on these fixtures. However, behavioral success remained 0/10 and no eligible run produced a repository delta. Five stability-002 runs proposed ungrounded placeholder replacements and were rejected. Five stability-003 runs proposed exact-match no-op replacements that the edit tool accepted but that produced no byte-level change. Subsequent outputs in both fixtures appeared to select plausible recovery actions (search_text or run_check) but violated Hewn's required JSON protocol.

The intervention therefore moved the observable failure boundary downstream rather than solving the tasks: from premature completion/action selection toward edit construction, grounding, effective mutation, and recovery protocol serialization. Because 013B-2 jointly changed rejected-response retention and controller-feedback role, it does not identify which representation change caused the action-selection improvement. It also does not establish an intrinsic model-capability boundary.


## 013C — Deterministic edit grounding

### Motivation

013B-2 changed the observable action-selection behavior of the model.

Across the 10 intervention-eligible runs, coherent completion-feedback
representation produced 10/10 post-intervention `replace_text` attempts,
compared with 0/10 in 013B-1.

Behavioral success nevertheless remained 0/10, and no eligible run produced a
repository delta.

The downstream failures differed across the two frozen mutation tasks.

For `stability-002`, the model selected `replace_text` but proposed replacement
targets that were not grounded in the repository contents. The edit was
therefore rejected before application.

For `stability-003`, the model selected `replace_text` using source text that
did exist, but proposed an exact-match no-op replacement. The tool accepted the
operation, but the repository contents did not change and the requested
behavior remained incorrect.

These observations motivate a controlled test of whether deterministic
repository grounding can move the failure boundary beyond edit construction
without supplying the semantic implementation.

### Research question

Can deterministic grounding support convert post-feedback edit intent into an
effective repository mutation, or does failure persist after mechanically
verified edit targets are available?

### Hypothesis

When a model proposes a `replace_text` edit that cannot produce an effective
repository mutation because its target is absent or its replacement is
identical to the existing text, deterministic feedback containing only
mechanically recoverable repository evidence may increase subsequent effective
edit attempts.

Behavioral success remains the primary outcome.

An increase in applicable or repository-changing edits without an increase in
behavioral success will be interpreted only as movement of the observable
failure boundary.

### Experimental unit

013C operates only after the model has independently selected `replace_text`.

The intervention does not select an edit tool for the model.

The intervention does not proactively identify a file, symbol, replacement, or
implementation before an edit attempt.

### Control

The control observation is the frozen 013B-2 treatment.

013B-2 already provides:

- coherent rejected-completion history;
- mutation-specific completion feedback;
- the existing repository context;
- the existing tool set;
- the existing `replace_text` interface;
- ordinary tool-result feedback;
- ordinary `CompletionRequirement.VERIFIED` behavior.

The frozen 013B-2 result is reused as the control observation.

No 013B-2 raw result is modified or regenerated.

### Treatment trigger

The grounding intervention is eligible only after all of the following are
true:

1. the task is one of the frozen mutation-required tasks;
2. the mutation-specific completion intervention has already been delivered;
3. the model subsequently selects `replace_text`;
4. the proposed edit does not produce an effective repository mutation for one
   of the two frozen mechanical reasons below.

The two eligible mechanical reasons are:

#### Missing target

The proposed `old` text does not occur in the requested file.

#### No-op replacement

The proposed replacement would leave the file contents unchanged.

This includes the frozen 013B-2 case in which `old == new`.

The intervention must not be triggered because an edit is semantically wrong,
because a hidden evaluator fails, or because the controller knows the expected
implementation.

### Treatment

For the first eligible ineffective `replace_text` attempt, Hewn supplies one
bounded deterministic grounding observation.

The observation may contain only information mechanically recoverable from:

- the model-selected file;
- the current contents of that file;
- the model-proposed edit;
- the deterministic reason the proposed edit could not produce an effective
  repository mutation.

For a missing-target edit, the controller feedback is:

> Controller grounding feedback: The requested replacement target was not found
> in the selected file. Re-read the current source and ground any replacement in
> text that exists exactly in that file.

For a no-op edit, the controller feedback is:

> Controller grounding feedback: The requested replacement would leave the
> selected file unchanged. Re-read the current source and make a replacement
> only if it produces an actual repository change.

The existing repository-reading and search tools remain available.

The intervention does not supply replacement text.

The intervention does not construct an edit on behalf of the model.

The intervention does not identify the correct implementation.

### Source-evidence constraint

013C may expose the current source only through mechanisms already available to
the model in the frozen tool/context interface.

The intervention must not introduce:

- expected replacement text;
- expected patch contents;
- hidden test output;
- behavioral-oracle output;
- evaluator-only information;
- a task-specific implementation hint;
- a symbol or file not independently selected or retrieved through the frozen
  interface;
- an automatically generated semantic repair.

If the model needs additional source evidence after grounding feedback, it must
obtain that evidence using the existing repository tools.

### Important distinction

013C distinguishes `edit attempt` from `tool-accepted edit call` from
`effective repository mutation` from `behaviorally correct mutation`.

These are separate measurements.

A tool call returning `ok=True` is not sufficient evidence that repository
contents changed.

### Bounded-intervention semantics

Grounding-specific feedback may be injected at most once per run.

The treatment behaves as follows:

1. 013B-2 coherent completion feedback operates unchanged.
2. The model independently selects `replace_text`.
3. Hewn evaluates the proposed edit mechanically.
4. If the edit is effective, no 013C grounding intervention is delivered.
5. If the edit has a missing target or is a no-op replacement, the first such
   attempt receives the frozen grounding feedback corresponding to that
   mechanical reason.
6. The next model response is the single additional action opportunity created
   by the grounding intervention.
7. After that response, grounding-specific intervention is exhausted.
8. Existing completion, verification, stagnation, protocol, and turn-budget
   behavior resumes unchanged.

The treatment does not increase `MAX_TURNS`.

It does not alter `max_stagnant_turns`.

It does not add retries after observing model output.

It does not automatically repair the proposed edit.

### Frozen tasks

Reuse the byte-equivalent 013B fixture set.

Grounding-intervention candidates:

- `stability-002`
- `stability-003`

`stability-001` remains a mutation-intervention-ineligible negative control.

All three tasks remain in the experiment so that unexpected treatment leakage
can be detected.

No task request or fixture content may be changed after 013C model outputs are
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
- repository fixtures;
- initial repository evidence;
- available tools;
- edit representation;
- completion requirement;
- maximum agent turns;
- stagnation threshold;
- mutation-specific completion feedback;
- coherent completion-feedback representation;
- behavioral evaluators;
- regression evaluators;
- structural evaluators;
- repetition count.

### Repetitions

Use five repetitions per frozen task, matching 011B, 013B-1, and 013B-2.

All frozen repetitions count.

Do not add retries, alter prompts, change fixtures, or expand the task set after
observing treatment outputs.

### Primary outcome

Behavioral success requires all of the following:

- requested task behavior passes;
- required regression checks pass;
- required structural checks pass, when present.

### Diagnostic measurements

Record separately:

- protocol validity;
- mutation-intervention eligibility;
- mutation-intervention delivery;
- grounding-intervention eligibility;
- grounding-intervention delivery;
- grounding reason;
- model calls;
- tool calls;
- edit attempts;
- tool-accepted edit calls;
- effective repository mutations;
- edit attempt after grounding intervention;
- task success;
- regression success;
- structural success;
- behavioral success;
- terminal reason;
- changed files;
- normalized repository diff;
- patch hash;
- wall time.

### Effective-mutation measurement

An effective repository mutation must be established from repository state, not
from the edit tool's success flag alone.

For a `replace_text` call, effective mutation means:

`file_bytes_after_edit != file_bytes_before_edit`

A no-op replacement therefore counts as:

- `edit_attempt = true`
- `tool_accepted_edit_call = true`
- `effective_mutation = false`

if the existing production tool accepts that operation.

This experiment must not silently redefine historical 013B-2 measurements.

### Interpretation

Possible outcomes include:

1. More effective mutations and more behavioral successes:

   Deterministic grounding improved the targeted mechanical boundary and
   downstream task completion on the frozen tasks.

2. More effective mutations but unchanged behavioral success:

   Grounding moved the observable failure boundary beyond mechanical edit
   construction, but semantic implementation correctness remains unresolved.

3. More grounded or applicable edit attempts but no effective repository
   mutations:

   The intervention changed edit construction without producing actual
   repository changes.

4. No movement beyond the original ineffective edit:

   Deterministic grounding, as represented in this treatment, did not resolve
   the observed edit-construction boundary.

5. New protocol failures, regressions, or unrelated behavior:

   The intervention introduced or exposed another failure mode and must not be
   treated as behavioral improvement.

No outcome from 013C alone establishes an intrinsic model-capability limit.

### Causal limitation

013C tests a bounded deterministic grounding intervention as a package.

If behavior changes, the experiment establishes an effect of the tested
grounding mechanism on the frozen tasks.

It does not establish that the same intervention is optimal for arbitrary edit
representations, models, repositories, or coding tasks.

### Production decision rule

A grounding mechanism earns consideration for production only if:

- it uses mechanically available repository state;
- it does not expose evaluator-only or expected-patch information;
- it remains bounded;
- it improves the targeted boundary without unacceptable regressions;
- its additional model/tool/resource cost remains visible.

A positive diagnostic result does not by itself justify a general automatic
repair system.

### Non-claims

013C does not establish:

- that deterministic grounding solves semantic reasoning;
- that every failed edit should receive additional model calls;
- that Hewn should generate replacement text deterministically;
- that source availability implies source understanding;
- that tool acceptance implies repository mutation;
- that repository mutation implies behavioral correctness;
- that protocol-valid recovery implies semantic recovery;
- that the tested model has reached an intrinsic capability limit;
- that results generalize beyond the frozen tasks and configuration.

### Design principle

> Deterministic mechanisms should establish whether an action is grounded and
> effective. The model should remain responsible for deciding what semantic
> change to make.
