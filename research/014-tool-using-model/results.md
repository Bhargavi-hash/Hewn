
## Local training feasibility

The first Module 14 LoRA training attempt did not produce a completed
training run.

Qwen2.5-Coder-0.5B-Instruct was trained using the frozen Module 14 pipeline
on the CPU-only target laptop with approximately 7.6 GiB RAM. During the
attempt, the interactive workstation became unresponsive and the editor
terminated.

No training process remained after recovery. Kernel logs inspected afterward
did not identify a specific OOM-killed process, so the event is not
classified as a confirmed kernel OOM failure.

Result:

    local CPU training: operationally impractical under tested configuration
    completed training run: no
    adapter produced: no
    behavioral result: not measured

No behavioral conclusion may be drawn from this attempt.

The primary Module 14 training experiment will continue on GPU-backed
hardware using the already frozen training and evaluation data.

## M14 held-out evaluation

### Training

- Base model: Qwen/Qwen2.5-Coder-0.5B-Instruct
- Method: LoRA supervised fine-tuning
- Training examples: 96
- Epochs: 1
- Optimizer steps: 12
- Final reported training loss: 4.3571
- GPU: Tesla T4
- Training runtime: 17.09 seconds
- Adapter size: approximately 28 MB

### Held-out evaluation

The evaluation contained 24 examples from families excluded from M14
training:

- 12 `search_after_rejection`
- 12 `completion_after_verification`

Results:

| Metric | BASE | M14 |
|---|---:|---:|
| Valid JSON | 0/24 | 12/24 |
| Correct action | 0/24 | 0/24 |
| Exact action | 0/24 | 0/24 |

Per-family M14 results:

| Family | Valid JSON | Correct action | Exact action |
|---|---:|---:|---:|
| search_after_rejection | 0/12 | 0/12 | 0/12 |
| completion_after_verification | 12/12 | 0/12 | 0/12 |

All 12 parseable `completion_after_verification` outputs collapsed to:

    {"action":"run_check"}

The expected action was a Hewn final action of the form:

    {"type":"final","text":"Implemented the requested change and verified the tests."}

### Interpretation

M14 changed output-format behavior but did not demonstrate held-out
tool-policy transfer.

The valid-JSON increase from 0/24 to 12/24 must not be interpreted as an
increase in correct tool use. None of the 24 held-out examples selected the
correct action.

The identical `run_check` response across the completion family is evidence
of an action-collapse failure under this training configuration.

The experiment therefore separates two capabilities:

1. producing structured-looking output;
2. selecting the correct Hewn action for the current agent state.

M14 showed evidence for the first but not the second.

No additional M14 epochs are selected based on this held-out result. Doing
so would turn the held-out evaluation into a tuning set.

### Decision

Preserve this M14 checkpoint and result as the one-epoch SFT result.

Proceed to Module 15 using the already frozen execution-derived recovery
dataset rather than modifying M14 against its held-out failures.

M15 remains supervised execution-derived recovery training, not
reinforcement learning.

The next comparison is:

    BASE vs M14 vs M15

with the M14 result retained unchanged.