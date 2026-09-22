# Module 13 Evidence and Claims

This file records the claims supported by Module 13 and the boundaries around
those claims.

Claims must remain traceable to frozen experiments and raw artifacts.

---

## Experimental provenance

### 013B-1: completion intervention

Experiment:

`research/013-small-model-failures/evaluate_completion_intervention.py`

Raw artifact:

`research/013-small-model-failures/results/013b-completion-intervention-run001.json`

Raw artifact SHA-256:

`6a51839ae5f918413a154b7939d08b354ff9e29656ac296da9e5ced3f11ab115`

Experiment implementation commit:

`c5c85de5a45b52a67dbe1b4d65f69dbdedf1ed8a`

---

### 013B-2: feedback representation

Experiment:

`research/013-small-model-failures/evaluate_feedback_representation.py`

Raw artifact:

`research/013-small-model-failures/results/013b-feedback-representation-run001.json`

Raw artifact SHA-256:

`8ffbdf1f5197331a175ef41daf28fbf44491fe444197aa21cfdab0779bfbc56f`

Experiment implementation commit:

`12cad3209a541fe8865c33b13a49f3ba83f2607e`

---

### 013C: deterministic edit grounding

Experiment:

`research/013-small-model-failures/evaluate_grounding_intervention.py`

Raw artifact:

`research/013-small-model-failures/results/013c-grounding-intervention-run001.json`

Raw artifact SHA-256:

`9e22c49e826c207d23ab6381a910c17a7d8448bc787f9e9971fc6b932d1f2cec`

Experiment implementation commit:

`a19a42c323a7b3e02352e868f659fb80e9e7bd82`

---

## Supported claims

### Claim 1: feedback representation affected observable action selection

On the 10 frozen mutation-required runs, the 013B-1 intervention produced zero
post-feedback edit attempts.

Under the 013B-2 feedback representation, all 10 corresponding eligible runs
produced a `replace_text` attempt after mutation-specific feedback.

Observed comparison:

| Metric | 013B-1 | 013B-2 |
| --- | ---: | ---: |
| Eligible runs | 10 | 10 |
| Feedback delivered | 10 | 10 |
| Post-feedback edit attempts | 0 | 10 |
| Behavioral successes | 0 | 0 |

Supported wording:

> On the frozen Module 13 fixtures, changing the tested completion-feedback
> representation changed post-feedback edit selection from 0/10 to 10/10
> eligible runs.

Not supported:

> User-role feedback is always better than tool-role feedback.

Not supported:

> Retaining rejected assistant responses alone caused the improvement.

013B-2 changed both rejected-response retention and controller-feedback role.

---

### Claim 2: improved action selection did not imply effective mutation

All 10 eligible 013B-2 runs attempted an edit after the intervention.

None produced a repository delta.

Five `stability-002` runs proposed replacement targets that were not present in
the selected file.

Five `stability-003` runs proposed exact-match no-op replacements.

Supported wording:

> The tested feedback representation improved observable action selection but
> did not produce an effective repository mutation or behavioral success on the
> eligible runs.

---

### Claim 3: tool acceptance and effective mutation are distinct

In all five `stability-003` runs in 013B-2, `replace_text` was accepted by the
tool even though the replacement left repository bytes unchanged.

Supported wording:

> A tool-accepted editing action is not sufficient evidence that repository
> state changed.

This claim is mechanical and scoped to the observed Hewn edit semantics.

---

### Claim 4: bounded deterministic grounding feedback did not produce a valid subsequent edit

013C delivered its frozen grounding observation in all 10 eligible runs.

No eligible run subsequently produced another valid edit attempt.

No eligible run produced an effective repository mutation.

Behavioral success remained zero.

Supported wording:

> On the frozen 013C fixtures, one bounded deterministic observation explaining
> either a missing replacement target or a no-op replacement did not produce a
> subsequent valid edit or effective repository mutation.

Not supported:

> Deterministic grounding does not work.

013C did not test stronger grounding mechanisms such as automatically supplying
an exact source span.

---

### Claim 5: failure boundaries moved while behavioral success remained unchanged

Across 013B-1, 013B-2, and 013C, behavioral success remained zero on all
intervention-eligible runs.

However, observable intermediate behavior changed.

013B-1 terminated without edit attempts.

013B-2 produced edit attempts but no repository deltas.

013C mechanically identified why those first edits were ineffective but exposed
subsequent recovery and protocol failures.

Supported wording:

> Intermediate failure-boundary measurements distinguished intervention effects
> that final behavioral pass/fail alone would have hidden.

---

### Claim 6: the experiments do not establish an intrinsic model-capability boundary

The interventions did not exhaust possible deterministic scaffolding,
alternative protocols, model training, stronger grounding, or other model
sizes.

Supported wording:

> Module 13 identifies observable failure boundaries under the tested Hewn
> configurations; it does not establish an intrinsic capability limit for the
> underlying model.

---

## Architecture conclusions supported by the evidence

The following design decisions are supported strongly enough to carry forward
into Hewn development:

1. Controller-feedback representation is part of the agent architecture and
   should not be treated as semantically irrelevant plumbing.

2. Hewn should distinguish edit attempts, tool-accepted edits, effective
   repository mutations, and behaviorally correct changes.

3. Deterministic mechanisms should establish mechanically knowable facts such
   as applicability, repository deltas, schema validity, authorization, and
   execution results.

4. Mechanical feedback should not silently contain evaluator-only semantic
   information.

5. Failure-boundary diagnostics should remain part of Hewn Bench rather than
   reporting only final behavioral success.

6. Small-model training should explicitly include Hewn's structured action and
   recovery protocol.

---

## Claims explicitly not earned

Module 13 does not support claims that:

- Hewn is better than Codex;
- Hewn is better than Claude Code;
- the tested 1.5B model is sufficient for repository-level coding;
- the tested 1.5B model is insufficient for repository-level coding;
- a larger local model would solve these tasks;
- protocol training alone will solve the tasks;
- deterministic grounding alone will solve the tasks;
- the frozen fixtures represent coding-agent workloads generally;
- zero-temperature inference is deterministic;
- the observed intervention effects generalize beyond the frozen tasks; or
- Module 13 demonstrates production-level coding-agent reliability.

These questions require later modules and broader evaluation.
