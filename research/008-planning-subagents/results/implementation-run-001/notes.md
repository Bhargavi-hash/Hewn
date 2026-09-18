# Experiment 008B Run 001 Notes

## Result

Direct implementation:

- behavioral oracle success: 1/8
- protocol valid: 7/8
- preflight valid: 6/8
- committed: 6/8
- mean required-file recall: 0.7500
- mean required-file precision: 0.7500
- unnecessary changed files: 0
- mean prompt characters: 1960.9
- total implementer inference time: 119.71 seconds

Plan-conditioned implementation:

- behavioral oracle success: 1/8
- protocol valid: 8/8
- preflight valid: 8/8
- committed: 8/8
- mean required-file recall: 0.9375
- mean required-file precision: 1.0000
- unnecessary changed files: 0
- mean prompt characters: 2555.9
- total implementer inference time: 123.48 seconds

The plan-conditioned implementer used approximately 30.3% more prompt
characters.

Planner inference cost is not included in these implementation timings because
008B replayed the frozen 008A plans.

## Interpretation

In this eight-task temperature-zero diagnostic, explicit plan conditioning
improved implementation mechanics but did not improve hidden behavioral-oracle
success.

The planned condition produced:

- higher protocol validity;
- higher deterministic-preflight validity;
- higher required-file recall;
- higher required-file precision.

However, both conditions passed the hidden behavioral oracle on only one task.

No task failed the behavioral oracle under direct implementation and passed it
under plan-conditioned implementation.

Therefore 008B does not provide evidence that a mandatory model-generated
planning stage improves behavioral implementation success for this model and
task set.

## Patch diagnostics

### plan-003

Planning expanded the implementation from incomplete/unappliable direct scope
to a committed cross-file change.

The resulting implementation was still semantically incorrect. It renamed the
public timeout function unnecessarily, left a stale timeout reference, and
corrupted the unrelated retry constant.

Classification: scope improvement without semantic correctness.

### plan-004

Planning produced a syntactically valid three-file implementation where the
direct condition produced invalid code.

The implementation nevertheless inverted authorization semantics by returning
the suspended flag directly and did not preserve inactive formatting.

Classification: mechanical improvement with semantic implementation failure.

### plan-005

Both conditions passed the hidden runtime oracle.

Both also incorrectly changed the visible explicit-TTL assertion from 15 to
120 even though runtime explicit-TTL behavior remained correct.

The hidden oracle measures runtime behavior but does not establish complete
task success for verification-surface edits.

Classification: runtime behavioral success with visible-test regression.

This limitation is preserved rather than retroactively changing the run.

### plan-006

The frozen plan named src/parser.py as an edit target and tests/test_parser.py
only as verification.

The plan-conditioned implementation changed only src/parser.py, matching that
scope omission. Its actual parser edit was also semantically invalid.

Classification: downstream scope omission consistent with planner omission,
plus independent implementation reasoning failure.

### plan-007

Both conditions produced the same ineffective import-only changes.

The frozen plan had correct file and symbol scope but represented each
operation only as "change the required behavior".

Classification: correct scope with semantically uninformative decomposition.

### plan-008

Planning produced a cleaner tool-level parameter than the direct condition,
but neither implementation propagated configuration through Session -> Agent
-> run_command.

Classification: multi-hop propagation reasoning failure.

## Conclusion

008A and 008B together separate repository scope from semantic implementation.

Deterministic structure slightly improved planning scope in 008A.

Explicit plan conditioning improved protocol behavior, applicability, and file
coverage in 008B.

Neither result demonstrated improved behavioral correctness.

For this diagnostic, a mandatory free-form planner call has therefore not
earned a permanent place in Hewn's execution path.

Planning may still be useful selectively for tasks whose decomposition cannot
be recovered mechanically.

## Limitation

The hidden behavioral oracle is the primary outcome for this frozen run, but
plan-005 demonstrates that runtime behavioral success does not necessarily
imply complete task success when the task itself requires modifying visible
verification code.

Run 001 remains unchanged.

Future benchmark design should distinguish runtime behavior, required
verification-surface changes, and complete task success explicitly.