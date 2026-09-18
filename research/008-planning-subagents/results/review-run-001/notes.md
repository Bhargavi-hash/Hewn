# 008C Run 001 Notes

## Experiment

008C tested whether an independent Qwen2.5-Coder-1.5B reviewer could
judge candidate patches from the frozen 008B implementation run.

Three reviewer conditions were evaluated:

1. `patch_only`
2. `execution_signal`
3. `execution_evidence`

Temperature was 0.0. Each candidate received one reviewer call with no
retry.

The reviewer produced a strict `accept` or `reject` verdict plus a short
reason.

## Corpus clarification

The frozen 008B results contain 14 committed candidate patches.

Two committed candidates were syntactically invalid and therefore never
reached hidden runtime verification:

- `plan-002__plan_conditioned`
- `plan-004__direct`

Accordingly:

- `patch_only` evaluated all 14 committed patches;
- `execution_signal` evaluated 12 runtime-verified patches;
- `execution_evidence` evaluated 12 runtime-verified patches.

Among the 12 runtime-verified candidates:

- 2 had runtime PASS labels;
- 10 had runtime FAIL labels.

The runtime label is a hidden behavioral-oracle result, not a claim of
complete task correctness.

In particular, the two plan-005 runtime-PASS candidates contain visible
verification-surface problems identified during manual patch inspection.

## Aggregate results

### Patch only

- protocol valid: 14/14
- true positive: 1
- true negative: 6
- false positive: 4
- false negative: 1
- runtime-pass recall: 0.50
- runtime-fail recall: 0.60
- balanced accuracy: 0.55
- accepts: 5
- rejects: 9
- mean prompt characters: 2052.9
- total model time: 134.17 seconds

### Execution signal

- protocol valid: 12/12
- true positive: 2
- true negative: 10
- false positive: 0
- false negative: 0
- runtime-pass recall: 1.00
- runtime-fail recall: 1.00
- balanced accuracy: 1.00
- accepts: 2
- rejects: 10
- mean prompt characters: 2114.6
- total model time: 77.16 seconds

### Execution evidence

- protocol valid: 11/12
- true positive: 2
- true negative: 9
- false positive: 0
- false negative: 0
- protocol failure: 1
- reported runtime-pass recall: 1.00
- reported runtime-fail recall: 0.90
- reported balanced accuracy: 0.95
- accepts: 2
- rejects: 9
- mean prompt characters: 2440.4
- total model time: 123.75 seconds

The execution-evidence metrics count the protocol failure as an
unrecovered runtime-fail case. They should not be interpreted as a
semantic false acceptance.

## Qualitative inspection

The patch-only reviewer was not consistently semantically grounded.

It falsely accepted:

- `plan-003__plan_conditioned`
- `plan-006__plan_conditioned`
- `plan-008__direct`
- `plan-008__plan_conditioned`

These include reference corruption, invalid YAML handling, and incomplete
multi-hop propagation.

The reviewer also sometimes produced a correct rejection for an incorrect
reason. For example, some explanations treated requested behavior such as
YAML support or repository-relative POSIX identifiers as if those changes
were forbidden.

Both syntax-invalid committed patches were rejected by the patch-only
reviewer. This is useful behavior, but deterministic syntax validation
already detects this class of failure without an additional model call.

The execution-signal condition reproduced the deterministic PASS/FAIL
signal exactly. This does not demonstrate additional reviewer capability:
Hewn already possesses the signal before reviewer inference.

Detailed normalized execution evidence did not improve verdict performance
over the one-bit execution signal. It increased context and model time and
introduced one protocol failure.

The protocol failure occurred for `plan-001__direct`. The model began a
valid JSON rejection and repeatedly elaborated the same explanation until
the response was truncated before the JSON object closed. The intended
verdict was visible as `reject`, but the frozen strict parser correctly
classified the response as invalid JSON. No retry was performed.

## Interpretation

In this small temperature-zero diagnostic, an independent 1.5B reviewer
did not demonstrate enough reliable semantic discrimination to justify a
mandatory reviewer inference.

Providing deterministic runtime PASS/FAIL made reviewer verdicts perfectly
match the runtime labels, but this largely duplicated information already
available to the agent.

Providing richer normalized execution evidence did not improve verdict
quality over the simpler signal and introduced additional context,
inference cost, and a protocol failure.

The evidence therefore does not support adding a mandatory model reviewer
after deterministic verification.

This result does not establish that model-based review is generally
ineffective. It is specific to this model, corpus, prompt, and single-run
diagnostic.

## 008D decision

008D full planner-implementer-reviewer orchestration is skipped.

008A showed a modest improvement in deterministic scope discovery when
repository structure was supplied.

008B showed that explicit plan conditioning improved protocol validity,
preflight success, commit rate, and required-file coverage, but did not
improve behavioral success over direct implementation.

008C showed that independent patch review was weak, while review after
execution largely duplicated deterministic verification.

Composing these stages would therefore add planner and reviewer inference
cost without evidence that either model stage improves end-to-end
behavioral success.

A full orchestration experiment can be revisited later if a planner,
implementer, or reviewer independently demonstrates a behavioral gain.