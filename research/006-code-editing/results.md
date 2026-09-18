# Module 6 Results

Results are recorded after each frozen experiment.

No production editing policy is selected before the corresponding experiment is run.

## Experiment 001 — Initial `replace_text` end-to-end baseline

### Configuration

- Model: Qwen2.5-Coder-1.5B-Instruct Q4_K_M
- Temperature: 0
- Tasks: 6 frozen editing fixtures
- Relevant source supplied in the initial request
- Editing primitive: `replace_text`
- Completion requirement: `VERIFIED`
- Runs per task: 1
- Repeated trials: no

### Results

| Metric | Result |
|---|---:|
| Behavioral success | 0/6 |
| Agent finalized | 0/6 |
| Tasks with an edit attempt | 0/6 |
| Tasks with an applied edit | 0/6 |
| `replace_text` attempts | 0 |
| Protocol failures | 6/6 |

All six tasks terminated with `ModelProtocolError` before any
`replace_text` invocation. Therefore the editing primitive received
zero treatment exposure.

### Protocol diagnostic

A separate single-task diagnostic was performed on `edit-001` to
inspect the raw model response without changing the parser.

The model returned a semantically valid Hewn final-response object
wrapped in a Markdown JSON fence. The strict protocol parser rejected
the response because Hewn requires exactly one JSON object with no
surrounding Markdown.

The response also claimed that the repository had been modified even
though no editing tool had been invoked.

This reveals two distinct pre-editing failures:

1. protocol formatting: the model wrapped the JSON object in a
   Markdown fence;
2. action/completion grounding: the model attempted to finalize and
   claimed that the modification had occurred without performing an
   edit.

### Interpretation

Experiment 001 does not provide evidence for or against the reliability
of `replace_text`. No editing operation was attempted.

Relaxing the JSON parser would not by itself solve the observed
failure. Removing the Markdown fence would make the diagnostic response
parseable, but it would still be an unsupported finalization with no
repository modification.

The next experiment should isolate editing representation from
independent action selection and completion behavior by requiring the
model to propose an edit before verification.