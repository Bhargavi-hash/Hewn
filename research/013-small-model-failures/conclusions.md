# Module 13 Conclusions: Why Small Models Fail

## Research question

> What failure modes prevent small coding models from completing
> repository-level tasks, and which of those failures can be mitigated
> deterministically through tools, context, decomposition, verification,
> or control-loop design?

Module 13 investigated small-model failure as an agent-system problem rather
than treating every unsuccessful run as evidence that the underlying model was
simply too weak.

The central design principle was:

> A model failure is not automatically an agent failure.

A coding-agent run crosses several observable boundaries between receiving a
task and producing a behaviorally correct repository change. Failure at one
boundary can prevent later capabilities from being exercised at all.
Accordingly, Module 13 classified failures by their earliest observable
boundary and then tested targeted interventions intended to move specific
boundaries without supplying hidden evaluator information or the desired
implementation.

The experiments do not establish an intrinsic capability limit for the tested
model. They establish that different agent interfaces can expose materially
different observable failure modes from the same model on the same frozen
tasks.

---

## Experimental scope

The intervention experiments used:

- Qwen2.5-Coder-1.5B-Instruct
- Q4_K_M quantization
- llama.cpp
- temperature 0
- 4096-token configured context window
- 4 inference threads
- the frozen Module 11 stability fixtures
- five repetitions per task
- unchanged hidden behavioral and regression evaluators
- unchanged repository tools
- unchanged maximum turn budget

The three frozen tasks were:

- `stability-001`, used as the negative control for mutation-specific
  interventions
- `stability-002`, a repository mutation requiring a grounded change to request
  retry behavior
- `stability-003`, a repository mutation requiring a semantic change to name
  normalization behavior

The experiments intentionally preserved failures and counted every frozen run.

---

## 1. Failure taxonomy

Module 13 began by freezing a taxonomy before intervention experiments.

The observable pipeline was:

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
    grounding / applicability
            ↓
    behavioral correctness
            ↓
    verification interpretation
            ↓
    recovery
            ↓
    completion decision

The frozen failure categories were grouped as follows.

### Input and evidence

#### Retrieval failure

Relevant repository evidence is not acquired.

#### Evidence-utilization failure

Relevant evidence is available to the model, but the resulting action does not
reflect it.

### Reasoning and decision

#### Decomposition failure

The task is scoped or decomposed incorrectly.

#### Action-selection failure

The model selects an inappropriate next action for the observable state.

#### Semantic-reasoning failure

The model reaches the relevant code and action boundary but proposes behavior
that does not satisfy the requested semantics.

### Action generation

#### Protocol failure

The intended action is not serialized according to Hewn's required model
protocol.

#### Edit-construction failure

The model selects an editing action but constructs an invalid or ineffective
edit.

#### Grounding failure

The proposed action is not grounded in repository state available through the
agent interface.

### Feedback and recovery

#### Verification-interpretation failure

Available execution or verification evidence is interpreted incorrectly.

#### Repair failure

A detected failure does not lead to a successful corrective change.

### Control

#### Stagnation

The run repeatedly makes no useful observable progress.

#### Premature completion

The model attempts to finish before the task's completion conditions have been
satisfied.

---

## 2. Historical failures were not one phenomenon

The historical analysis in 013A classified failures from earlier Hewn modules
using existing experiment artifacts.

Those failures occurred at several different observable boundaries, including:

- evidence utilization
- semantic reasoning
- edit construction
- grounding
- repair
- protocol serialization
- premature completion

This matters because a final benchmark result such as "task failed" discards
information needed to improve the agent.

Two failed runs can require completely different interventions.

A retrieval failure may justify better repository search.

A grounded but semantically incorrect patch may require stronger model
reasoning or training.

A malformed tool call may require protocol specialization.

A correct failure diagnosis followed by an ineffective repair may require
recovery training or a different control loop.

The taxonomy therefore treats behavioral failure as the final outcome, not as
the failure explanation.

---

## 3. 013B-1: targeted completion feedback was insufficient under the original representation

013B-1 tested whether mutation-specific completion feedback could prevent the
model from completing a mutation-required task without first attempting an
edit.

The frozen feedback stated:

> The task requires a repository modification, but no edit has been attempted.
> Use an available repository-editing action before completing the task.

The intervention was delivered in all 10 eligible runs.

| Metric | Eligible runs |
| --- | ---: |
| Mutation feedback delivered | 10/10 |
| Edit attempted after feedback | 0/10 |
| Effective repository mutation | 0/10 |
| Behavioral success | 0/10 |

The intervention therefore did not improve observable action selection under
the original feedback representation.

Post-experiment implementation inspection exposed an important competing
explanation.

Rejected assistant final responses were not retained in conversational history,
while the controller rejection was represented as a `tool` message despite no
corresponding tool call.

The experiment therefore could not isolate model capability from feedback
representation.

This observation motivated 013B-2 without modifying or rerunning 013B-1.

---

## 4. 013B-2: feedback representation changed action selection

013B-2 preserved the information supplied by the intervention but changed its
representation.

The treatment jointly:

1. retained the rejected final response as an assistant message; and
2. represented deterministic controller feedback as a user message.

All other frozen controls remained unchanged.

Results on the 10 intervention-eligible runs:

| Metric | 013B-1 | 013B-2 |
| --- | ---: | ---: |
| Mutation feedback delivered | 10/10 | 10/10 |
| Post-feedback edit attempts | 0/10 | 10/10 |
| Tool-accepted edit calls | 0/10 | 5/10 |
| Effective repository mutations | 0/10 | 0/10 |
| Behavioral successes | 0/10 | 0/10 |

This is the clearest positive causal result in Module 13.

Changing the tested feedback representation changed observable action
selection on the frozen fixtures.

The result does not establish that either representation component is
individually responsible because rejected-response retention and controller
message role changed together.

It also did not solve the tasks.

Instead, the failure boundary moved downstream.

### `stability-002`

The model selected `replace_text`, but proposed placeholder replacement text
that did not exist in the selected file.

The edit was rejected.

### `stability-003`

The model selected `replace_text` using existing source text, but proposed the
same text for both `old` and `new`.

The tool accepted the exact replacement, but repository bytes did not change.

This exposed an important measurement distinction:

    edit attempt
        ≠
    tool-accepted edit
        ≠
    effective repository mutation
        ≠
    behaviorally correct mutation

A successful tool return is therefore insufficient evidence that repository
state changed.

---

## 5. 013C: deterministic grounding feedback did not produce effective recovery

013C tested the next exposed boundary.

After the model had independently selected `replace_text`, Hewn mechanically
identified one of two ineffective-edit conditions:

- the requested replacement target did not occur in the selected file; or
- the replacement would leave the selected file unchanged.

The intervention supplied one bounded deterministic observation explaining the
mechanical problem.

It did not provide:

- expected replacement text
- an expected patch
- hidden evaluator information
- a semantic implementation
- automatic repository retrieval
- automatic edit repair

The intervention was delivered in all 10 eligible runs.

| Metric | Eligible runs |
| --- | ---: |
| Grounding feedback delivered | 10/10 |
| Valid edit attempted after grounding | 0/10 |
| Effective repository mutations | 0/10 |
| Behavioral successes | 0/10 |

The negative-control `stability-001` runs received neither mutation-specific
nor grounding-specific intervention and produced no tool calls or repository
changes.

### `stability-002`

All five runs first produced an ungrounded placeholder `replace_text`.

After receiving the missing-target grounding observation, the subsequent raw
model output was another textual `replace_text` action using the same kind of
placeholder replacement.

The output violated Hewn's required JSON protocol.

There was no observable evidence of an intervening repository evidence
acquisition action.

### `stability-003`

All five runs first produced an exact-match no-op `replace_text`.

After receiving the no-op grounding observation, the model returned another
`FinalResponse("None")`.

Following ordinary completion rejection, it emitted a textual `run_check`
action outside Hewn's required JSON protocol.

The grounding intervention therefore did not produce a valid subsequent edit
or effective repository mutation.

---

## 6. The failure boundary can move without the task succeeding

The most important Module 13 result is the sequence across the intervention
experiments.

### 013B-1

    premature completion
            ↓
    mutation-specific feedback
            ↓
    no edit selected

### 013B-2

    premature completion
            ↓
    coherent feedback representation
            ↓
    edit selected
            ↓
    mechanically ineffective edit

### 013C

    premature completion
            ↓
    coherent feedback representation
            ↓
    edit selected
            ↓
    mechanical failure identified
            ↓
    recovery / protocol serialization failure

Behavioral success remained zero throughout these intervention experiments.

If evaluation recorded only behavioral success, every treatment would appear
identical.

They were not identical.

013B-2 changed the observable action boundary from no edit attempt to an edit
attempt in all 10 eligible runs.

013C then exposed what happened when the mechanical reason for those ineffective
edits was explicitly identified.

This demonstrates why coding-agent evaluation should retain intermediate
failure boundaries rather than reducing runs to a single pass/fail metric.

---

## 7. What deterministic scaffolding did and did not accomplish

Module 13 supports a narrow but important distinction.

### Deterministic scaffolding can change model behavior

The 013B experiments show that agent-interface design can materially alter the
actions produced by the same model on frozen tasks.

The model therefore cannot be evaluated independently of the control loop and
message representation surrounding it.

### Mechanical knowledge does not imply successful recovery

013C supplied mechanically valid information about why the proposed edit was
ineffective.

That information alone did not produce a valid recovery sequence.

Knowing that a target is absent is different from:

1. deciding to acquire current source evidence;
2. selecting the correct repository tool;
3. serializing the action correctly;
4. using the returned evidence;
5. constructing a grounded semantic edit; and
6. verifying the resulting behavior.

A deterministic controller can establish mechanical facts without thereby
supplying the semantic reasoning required to finish the task.

---

## 8. Implications for Hewn architecture

### Preserve coherent controller interactions

Rejected model responses and deterministic controller feedback should form a
coherent conversation.

013B-2 provides evidence that representation at this boundary affects
observable action selection.

This does not establish one universally optimal message representation, but it
does reject treating feedback representation as an irrelevant implementation
detail.

### Separate tool acceptance from repository mutation

A successful editing-tool return must not automatically be interpreted as an
effective repository change.

Hewn should distinguish at least:

- edit attempted
- edit accepted by the tool
- repository bytes changed
- requested behavior changed correctly

The production semantics exposed by 013B-2, where an exact no-op replacement
can return success, should eventually be hardened using this distinction.

That hardening should be treated separately from the frozen Module 13
experiments.

### Deterministic mechanisms should own mechanical facts

Hewn can deterministically determine whether:

- a replacement target exists;
- a replacement changes repository bytes;
- a test passed;
- a file changed;
- a proposed path is authorized; and
- an action conforms to a schema.

The model should not be asked to infer these facts when the system can know them
directly.

### The model remains responsible for semantic decisions

Mechanical grounding should not silently become an oracle for the desired
implementation.

The model must still decide:

- what behavior needs to change;
- which evidence is relevant;
- what semantic edit to make; and
- how to recover after failure.

This preserves the architectural boundary:

> Deterministic mechanisms establish whether an action is grounded and
> effective. The model remains responsible for deciding what semantic change
> to make.

---

## 9. Implications for training

Module 13 turns several observed failures into concrete training targets for
Module 14.

Training should not optimize only for final code generation.

The model must learn Hewn's action language and recovery process.

Priority training targets are:

### Structured tool serialization

Given an intended repository action, emit the exact structured protocol
required by Hewn rather than a natural-language approximation.

### Evidence acquisition after grounding failure

When an edit target is absent, select an appropriate repository-reading or
search action before attempting another replacement.

### Grounded edit construction

Construct `replace_text` operations from source text that actually exists in
the selected file.

### Effective mutation awareness

Avoid edits where the replacement is identical to the matched source.

### Tool-failure recovery

Treat failed tool execution as new evidence and select a valid next action
rather than prematurely completing or repeating an ungrounded operation.

### Verification discipline

After an effective mutation, use the available verification mechanisms before
claiming completion when the task requires verification.

### Completion discipline

Do not emit a final response merely because an implementation has been
described or intended. Completion should follow observable agent state.

These targets are narrower and more measurable than the objective "make the
small model better at coding."

---

## 10. What Module 13 does not establish

Module 13 does not show that:

- Qwen2.5-Coder-1.5B has reached an intrinsic capability limit;
- deterministic grounding is generally ineffective;
- larger models would solve the frozen tasks;
- a particular feedback role is universally optimal;
- repository retrieval alone would solve the observed failures;
- protocol specialization alone would produce behavioral success;
- tool acceptance implies repository mutation;
- repository mutation implies behavioral correctness;
- temperature 0 makes runs deterministic;
- these three fixtures represent repository-level coding tasks generally; or
- Hewn can yet match frontier coding agents.

The experiments are deliberately narrow.

Their purpose is to isolate observable agent boundaries, not to make broad
claims about model intelligence.

---

## 11. Module 13 answer

Small coding models do not fail at one universal "reasoning" boundary.

Across Hewn's historical and controlled experiments, failures appeared at
evidence utilization, decomposition, action selection, protocol serialization,
edit construction, grounding, semantic correctness, recovery, and completion
control.

Some of these boundaries can be changed by the agent system.

Most notably, 013B changed post-feedback edit selection from 0/10 eligible runs
under the original representation to 10/10 under the tested coherent
representation.

That improvement did not produce effective repository mutations or behavioral
success.

When 013C then supplied deterministic information explaining why those edits
were mechanically ineffective, no eligible run produced a subsequent valid
edit or effective mutation.

The evidence therefore supports a layered view of small-model coding-agent
failure:

> Agent scaffolding can remove or move specific failure boundaries, but moving
> one boundary does not imply that downstream capabilities are sufficient to
> complete the task.

This is the design foundation for the next stage of Hewn.

Module 14 should not attempt to train a generic coding model from scratch.

It should train the model specifically for the observable behaviors that the
agent system cannot reliably obtain through deterministic mechanisms alone:
structured tool use, evidence acquisition, grounded editing, recovery, and
verification-aware completion.
