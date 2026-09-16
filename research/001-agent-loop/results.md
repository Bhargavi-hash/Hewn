# Results — Research 001

## Environment

- CPU: Intel Core i5-10210U
- Physical cores: 4
- Hardware threads: 8
- System memory: 7.6 GiB
- GPU: Intel UHD integrated graphics
- NVIDIA GPU: none detected

## Initial Local Model

- Model: Qwen2.5-Coder-1.5B-Instruct
- Format: GGUF
- Quantization: Q4_K_M
- Runtime: llama.cpp
- Inference threads: 4

## Raw Inference Baseline

Simple Python generation produced a correct implementation.

Observed llama.cpp performance:

- Prompt processing: 31.4 tokens/s
- Generation: 11.1 tokens/s
- Maximum resident set size: 2,697,396 KB
- Swap operations reported by `/usr/bin/time`: 0

This establishes that a roughly 1.5B parameter, 4-bit coding model can
run interactively on the baseline CPU-only development machine.

## Initial Hewn Protocol Probe

The model was instructed to locate `ToolExecutor` using the available
`search_text` tool and to respond with exactly one Hewn JSON response.

Expected next action:

```json
{
  "type": "tool_call",
  "name": "search_text",
  "arguments": {
    "query": "ToolExecutor"
  }
}
```

Observed response:
```json
{
  "type": "final",
  "text": "Search_text(query: 'ToolExecutor')"
}
```

The model additionally wrapped the response in a Markdown JSON code fence.

## Observed Failure Modes
### Protocol formatting failure

The model did not obey the requirement that its response contain only
the JSON object. It emitted Markdown fencing around the object.

### Action encoding failure

The model appeared to identify repository search as the appropriate
next action, but represented that action as a final answer rather than
as a tool_call.

This distinction is important: the failure was not simply inability to
identify a useful operation. The model demonstrated partial semantic
understanding of the requested action while failing to express that
decision through Hewn's action protocol.

### Initial Observation

Small-model coding ability and reliable agent-protocol behavior are
separable capabilities.

This single probe is not sufficient to estimate failure rates. Repeated
controlled trials are required before making quantitative claims.

## Baseline 001 — Tiny Repository Bug Fix

### Environment

Model:
Qwen2.5-Coder-1.5B-Instruct-GGUF Q4_K_M

Inference:
llama.cpp / llama-server

Hewn tools:
- list_directory
- read_file
- search_text
- replace_text
- run_check

Task repository:
Two-file Python repository containing an intentionally incorrect
implementation of `add`.

Task:

> Fix the failing tests. Inspect the repository, make the necessary code
> change, run the tests to verify the fix, and only finish after the tests
> pass.

### Result

FAIL

Metrics:

- model calls: 1
- tool calls: 0
- successful tool calls: 0
- failed tool calls: 0
- wall time: 7.23 seconds

Model response:

`FinalResponse(text='Fixing failing tests in the repository...')`

Independent verification:

- `calculator.py` remained unchanged.
- `pytest` reported 2 failed tests.
- `git diff` showed no modification.

### Failure Classification

`PREMATURE_FINALIZATION`

The model returned a syntactically valid `FinalResponse` before inspecting
the repository or executing any tools.

### Observation

The failure occurred before repository inspection, diagnosis, editing, or
verification. Therefore this run does not provide evidence about the
quality of the editing or command-execution tools.

The same model previously produced a valid `search_text` tool call for a
repository-navigation task, suggesting that protocol generation itself is
possible but tool use is not yet reliable across task types.

## Baseline 002 — Behavioral Completion Instructions

### Intervention

Baseline 002 used the same model, repository, tools, inference settings,
and user task as Baseline 001.

The only intended intervention was the addition of behavioral instructions
to the Hewn system prompt clarifying that:

- repository tasks should use tools when inspection or modification is required;
- a final response means the requested task is complete;
- coding tasks should inspect repository evidence before editing; and
- requested verification should occur before finishing.

### Result

**FAIL**

Metrics:

- Model calls: 2
- Tool calls: 1
- Successful tool calls: 0
- Failed tool calls: 1
- Wall time: 11.72 seconds

Execution trace:

1. The model selected `run_check` with `{"check": "tests"}`.
2. `pytest` executed and reported two failing tests.
3. The failure output was returned to the model.
4. The model returned a `FinalResponse` without inspecting or modifying
   repository files.

Independent verification:

- `calculator.py` remained unchanged.
- `pytest` still reported 2 failed tests.
- `git diff` showed no modification.

### Failure Classification

`PREMATURE_FINALIZATION_AFTER_OBSERVATION`

Unlike Baseline 001, the model performed an appropriate initial tool action
and received useful repository evidence. It nevertheless finalized before
diagnosing or modifying the implementation.

### Comparison with Baseline 001

Baseline 001:

- 1 model call
- 0 tool calls
- finalized before repository interaction

Baseline 002:

- 2 model calls
- 1 tool call
- executed the requested test check
- observed detailed test failures
- finalized before repository inspection or modification

The behavioral system-prompt intervention therefore changed the observed
trajectory from immediate finalization to initial tool use in this trial,
but was insufficient to produce a complete coding-agent loop.

### Observation

The model's final response instructed the user to review and modify the
code rather than continuing to use its own available tools. This suggests
a possible mismatch between conversational-assistant behavior and the
autonomous-agent role expected by Hewn.

This is a single trial and does not establish the frequency or cause of
that behavior.

### Repeated Trials

To determine whether the Baseline 002 trajectory was an isolated model
response, the same experiment was repeated three additional times.

The repository was reset to the original failing state before each trial.
The model, quantization, inference configuration, system prompt, user
request, available tools, and repository contents were held constant.

| Trial | Model Calls | Tool Calls | Tool Sequence | Edit | Final Tests | Result |
|---|---:|---:|---|---|---|---|
| 1 | 2 | 1 | `run_check` | No | 2 failed | FAIL |
| 2 | 2 | 1 | `run_check` | No | 2 failed | FAIL |
| 3 | 2 | 1 | `run_check` | No | 2 failed | FAIL |
| 4 | 2 | 1 | `run_check` | No | 2 failed | FAIL |

Observed wall-clock times were approximately 11.7–12.7 seconds per run.

All four observed Baseline 002 trials followed the same trajectory:

1. Call `run_check` with the `tests` check.
2. Observe two failing pytest tests.
3. Return a `FinalResponse`.
4. Perform no repository inspection or modification.

The final response also remained effectively identical across the observed
trials, instructing the user to review and modify the code rather than
continuing to use Hewn's available tools.

### Repeated-Trial Observation

Within these four controlled trials, the behavioral prompt intervention
produced a stable but incomplete agent trajectory.

The model reliably initiated verification but did not continue from failed
verification into repository inspection, diagnosis, or editing.

Four trials are insufficient for a general statistical claim about the
model. They do, however, provide enough repeated evidence to motivate
testing whether Hewn's control layer can prevent premature completion when
environmental evidence contradicts completion.

### Baseline 003 — Deterministic completion policy

#### Intervention

Baseline 003 retained the Baseline 002 model, task, tool vocabulary,
behavioral prompt, and 20-turn limit.

The agent added a deterministic completion policy:

- failed verification moves the policy to `FAILED`;
- successful repository modification moves it to `STALE`;
- successful verification moves it to `PASSED`;
- final responses are rejected while verification is `FAILED` or `STALE`.

The purpose was to test whether Hewn could prevent premature completion
without changing the underlying model.

#### Trial 1

Result: **FAIL**

- Reached the 20-turn limit.
- Final repository remained unchanged.
- Independent verification: 2 tests failed.
- Detailed trajectory was unavailable because turn-limit failures did not
  preserve/expose telemetry.

This trial exposed an observability limitation in the experimental harness.
The harness was updated so turn-limit failures preserve and expose run
metrics and trace information.

During regression testing of that change, rapid Python source edits also
exposed stale bytecode during immediate re-verification. The Python test
check was changed to execute through the current interpreter with bytecode
caching disabled so verification reflects the current source state.

These changes affected observability and verification correctness rather
than the model's action policy.

#### Trial 2

Result: **FAIL**

Run metrics:

- Model calls: 20
- Tool calls: 1
- Successful tool calls: 0
- Failed tool calls: 1
- Wall time: 70.46 seconds
- Final independent verification: 2 tests failed
- Repository modification: none

Observed trajectory:

1. The model invoked `run_check("tests")`.
2. Verification reported both calculator tests failing.
3. The model proposed a final response telling the user that the tests
   failed and that the code should be fixed.
4. Hewn rejected finalization because the latest verification had failed.
5. On subsequent turns, the model repeatedly returned the completion-policy
   rejection text itself as a `FinalResponse`.
6. Hewn rejected each attempted finalization.
7. The run exhausted the 20-turn budget without another tool call.

#### Observation

The completion policy changed the failure mode but did not solve the task.

Without the policy, the model terminated immediately after observing failed
verification. With the policy, Hewn correctly prevented that termination,
but the model did not recover into further repository interaction.

This separates two capabilities:

1. **Completion correctness:** whether the harness permits an unsupported
   claim of completion.
2. **Recovery capability:** whether the model can choose a productive next
   action after completion is rejected.

Baseline 003 improved the first but provided no evidence of improvement in
the second.

The repeated trajectory is classified as:

`COMPLETION_REJECTION_LOOP`

Within this trial, 20 model calls resulted in only one environment tool
call. After the first rejected final response, subsequent turns made no
observable repository progress.