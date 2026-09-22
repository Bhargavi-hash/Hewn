
## M15 held-out recovery evaluation

### Training

- Base model: Qwen/Qwen2.5-Coder-0.5B-Instruct
- Training method: LoRA supervised fine-tuning
- Training rows: 192
- Original M14 rows: 96
- Execution-derived recovery rows: 96
- Epochs: 1
- Optimizer steps: 24
- Final reported training loss: 4.0417
- GPU: Tesla T4
- Training runtime: 31.4 seconds
- Adapter size: approximately 28 MB

M15 was trained from the original base model rather than by continuing the
M14 adapter. This keeps the intervention interpretable: M15 differs by its
training dataset rather than by an additional stage of adapter training.

### Frozen primary evaluation

The held-out recovery evaluation contained 32 examples:

- 8 missing_target
- 8 noop_edit
- 8 unverified_mutation
- 8 failed_verification

Results:

| Condition | Valid JSON | Correct action | Exact action |
|---|---:|---:|---:|
| BASE | 24/32 | 0/32 | 0/32 |
| M14 | 32/32 | 0/32 | 0/32 |
| M15 | 32/32 | 0/32 | 0/32 |

The predeclared primary metric, exact action correctness, therefore showed
no improvement for M15.

M15 must not be reported as succeeding on the frozen primary metric.

### Post-hoc output diagnostic

Inspection of the raw outputs revealed information that the strict primary
metric intentionally does not capture.

For `missing_target`, M15 selected the semantic operation `read_file` in all
8 examples, but represented it using a noncanonical schema such as:

    {"action":"read_file","file":"src/heldout_recovery_0.py"}

instead of the required Hewn action:

    {"type":"tool","name":"read_file","arguments":{"path":"src/heldout_recovery_0.py"}}

For `failed_verification`, M15 again selected `read_file` in all 8 examples,
but used another noncanonical representation such as:

    {"args":["src/heldout_recovery_0.py"],"tool":"read_file"}

For `noop_edit`, 5 of 8 outputs clearly selected `read_file`; the remaining
3 produced replace_text-like structures.

For `unverified_mutation`, M15 did not learn the required recovery policy.
All 8 expected `run_check`, while the generated outputs were read_file-like.

This diagnostic was performed after observing the frozen primary results.
It is therefore descriptive and must not replace or redefine the primary
metric.

### Interpretation

The experiment exposes three separable capabilities:

1. producing parseable structured output;
2. selecting an appropriate semantic recovery operation;
3. emitting that operation using Hewn's exact action schema.

M14 primarily improved structured-output compliance while retaining strong
action collapse.

M15 changed the learned policy. On two recovery families it consistently
selected the intended semantic operation, and on a third it usually moved
toward that operation. However, it failed to serialize those choices into
Hewn's canonical action schema and failed semantically on
`unverified_mutation`.

Therefore the strongest supported conclusion is:

Execution-derived supervised recovery examples changed state-conditioned
action behavior under this experiment, but did not produce a model capable
of reliably emitting executable Hewn actions.

The strict primary result remains 0/32 exact actions.

### Decision

Do not tune M15 against this held-out evaluation.

Preserve BASE, M14, and M15 as measured.

The next system-design implication is that Hewn should not assume a small
fine-tuned model can independently satisfy both semantic policy selection
and exact action serialization.

Module 16 should investigate how the complete Hewn system can combine model
reasoning with deterministic schema enforcement, tool authority, retrieval,
editing, execution feedback, and the other mechanisms established in
Modules 1 through 15.
