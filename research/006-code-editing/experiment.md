# Module 6 Experiments

## Experiment 001 — Exact-once replacement baseline

### Question

Where does Hewn's existing `replace_text` primitive fail when a small coding model performs repository editing tasks with the relevant source already available?

### Independent variable

Task editing shape.

The editing mechanism remains fixed as `replace_text`.

### Controlled factors

- coding model;
- temperature;
- agent implementation;
- editing tool;
- verification mechanism;
- source availability;
- task wording style;
- one run per task in the initial diagnostic experiment.

The relevant target source is supplied to the model so that the experiment primarily measures editing behavior rather than repository retrieval.

### Initial task shapes

1. unique localized expression change;
2. repeated expression requiring target disambiguation;
3. insertion of validation into an existing function;
4. modification of a multi-line conditional;
5. two related changes in one file;
6. coordinated changes across two files.

Tasks describe required behavior rather than specifying exact replacement strings.

### Isolation

Each task is represented by a pristine fixture repository.

For every evaluation run:

1. copy the fixture to a temporary workspace;
2. run the agent against the temporary copy;
3. execute mechanical verification;
4. compare the resulting workspace with the pristine fixture;
5. record metrics;
6. discard the temporary workspace.

The Hewn source tree is never modified by benchmark execution.

### Outcome taxonomy

- `no_edit`
- `application_failure`
- `applied_wrong_location`
- `invalid_code`
- `verification_failure`
- `success_with_extra_changes`
- `success`

The evaluator should distinguish editing-tool application from behavioral correctness.

### Metrics

Record at least:

- task success;
- whether an edit was attempted;
- edit application successes;
- edit application failures;
- model calls;
- tool calls;
- failed tool calls;
- files modified;
- lines added;
- lines deleted;
- verification result;
- syntax/parse result where applicable;
- final diff;
- wall time.

### Interpretation constraint

Experiment 001 is diagnostic.

It does not compare editing mechanisms and cannot establish that `replace_text` is better or worse than patches, whole-file generation, or structured editing.

Its purpose is to determine which concrete failure modes, if any, justify the next editing abstraction.