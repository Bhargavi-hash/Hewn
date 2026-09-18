# 008A Run 002 Notes

## Status

Valid measured planning-quality run.

All 16 calls completed successfully:

- 8 source-only;
- 8 source-plus-structure.

Strict protocol validity was 16/16.

## Protocol intervention

Run 001 produced Markdown-fenced JSON in all 16 calls and therefore had
0/16 strict protocol validity.

Run 002 strengthened only the serialization instruction. The parser remained
strict and no response repair or Markdown stripping was introduced.

Protocol validity increased from 0/16 in run 001 to 16/16 in run 002.

This demonstrates that, in this diagnostic, a concrete output contract was
sufficient to expose structured planning output from the model without
weakening the protocol.

## Planning results

### Source only

- protocol validity: 8/8
- mean required-file recall: 0.8125
- mean required-file precision: 1.0
- mean required-symbol recall: 0.7917
- mean verification recall: 0.8958
- mean verification precision: 1.0
- unnecessary files: 0
- mean prompt characters: 1374.875
- total latency: 81.88 seconds

### Source plus deterministic structure

- protocol validity: 8/8
- mean required-file recall: 0.875
- mean required-file precision: 1.0
- mean required-symbol recall: 0.8542
- mean verification recall: 0.8958
- mean verification precision: 1.0
- unnecessary files: 0
- mean prompt characters: 1559.25
- total latency: 65.96 seconds

The structural condition used approximately 13.4% more prompt characters.

The observed latency difference is not interpreted causally because this is
a single run.

## Task-level interpretation

The required-file recall improvement came from plan-003.

Without structure, the model planned only src/client.py.

With structure, it included both src/client.py and src/config.py, recovering
the missing cross-file dependency.

However, the structured plan described both operations only as "change the
required behavior", while the source-only plan contained a more concrete
client-side operation.

This means improved scope recall did not clearly correspond to improved
semantic operation quality.

Other examples reinforce the distinction between repository scope and plan
semantics:

- plan-004 identified the required three-file change but did not explicitly
  encode the requirement that suspended accounts must be denied access;
- plan-005 identified tests/test_cache.py as verification but did not plan
  the required test-file modification;
- plan-006 similarly identified tests/test_parser.py as verification but did
  not include it as a file requiring modification;
- plan-008 identified the complete three-source-file propagation path in both
  conditions but omitted tests/test_tools.py from verification.

## Conclusion

In this eight-task single-run diagnostic, deterministic repository structure
produced a small improvement in required-file and required-symbol recall while
preserving perfect required-file precision.

The required-file improvement was concentrated in one cross-file task.
Verification recall was unchanged.

Qualitative inspection did not show a corresponding improvement in semantic
operation quality.

The evidence therefore supports treating deterministic structure as a
potential grounding aid for scope discovery, not as evidence that structure
improves planning reasoning or downstream implementation correctness.

The next experiment must measure whether an explicit plan improves actual
implementation behavior.