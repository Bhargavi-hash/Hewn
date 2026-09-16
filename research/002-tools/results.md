## Experiment 001 — Primitive Tool Vocabulary

### Question

How effectively can the fixed local model solve repository-navigation tasks
using only the primitive Module 1 tool vocabulary?

### Tool Vocabulary

- `list_directory`
- `read_file`
- `search_text`
- `replace_text`
- `run_check`

No semantic repository-navigation tools are available.

### Task Set

Nine Hewn self-navigation tasks:

- 5 exact-symbol navigation tasks
- 4 conceptual navigation tasks

### Evaluation

A task passes when the final response contains both its expected file path
and expected symbol.

This evaluator is intentionally simple and deterministic.

### Controlled Variables

- Model: Qwen2.5-Coder-1.5B-Instruct
- Quantization: Q4_K_M
- Inference backend: llama.cpp
- Temperature: 0
- Tool vocabulary: Module 1 primitive tools
- Workspace: Hewn repository
- Completion requirement: NONE

### Observed Results

Overall deterministic task success: **0/9**.

| Task | Category | Outcome | Model Calls | Tool Calls | Primary Failure |
|---|---|---:|---:|---:|---|
| nav-001 | symbol | FAIL | unavailable | unavailable | protocol encoding |
| nav-002 | symbol | FAIL | 2 | 1 | tool-schema mismatch |
| nav-003 | symbol | FAIL | 2 | 1 | schema mismatch + hallucinated path |
| nav-004 | symbol | FAIL | 2 | 1 | tool-schema mismatch |
| nav-005 | symbol | FAIL | 2 | 1 | tool-schema mismatch |
| nav-006 | concept | FAIL | unavailable | unavailable | unsupported final / protocol encoding |
| nav-007 | concept | FAIL | unavailable | unavailable | unsupported final / hallucinated architecture |
| nav-008 | concept | FAIL | unavailable | unavailable | unsupported final / protocol encoding |
| nav-009 | concept | FAIL | unavailable | unavailable | unsupported final / protocol encoding |

### Important Observations

The 0/9 aggregate score does not represent a single failure mode.

For four of the five exact-symbol tasks, the model selected `search_text` as
its first action. This suggests that the primitive search operation was
conceptually appropriate for these tasks, although the model frequently failed
to conform to its argument schema.

For nav-002, nav-004, and nav-005, the model supplied both `query` and `path`
arguments even though `search_text` accepts only `query`. The model therefore
selected the intended operation but produced an incompatible tool interface.

Nav-003 additionally supplied a hallucinated Java-style source path before
observing the repository.

Nav-001 requested the appropriate `search_text` operation and query but wrapped
the otherwise structured response in a Markdown JSON fence, which the strict
Module 1 model protocol rejects.

The conceptual-navigation tasks showed a different pattern. The model often
attempted to answer from prior assumptions rather than inspect repository
evidence. Observed unsupported claims included a `Hewn` class,
`can_return_final_answer`, and `execute_action`, none of which were established
through repository observations in these runs.

Several conceptual responses were also wrapped in Markdown fences or otherwise
failed the strict response protocol.

### Current Interpretation

Experiment 001 does not yet provide evidence that exact-symbol navigation
requires a new `find_symbol` tool.

Instead, the traces expose at least four distinct limitations:

1. protocol encoding failures,
2. mismatch between the model's expected search interface and Hewn's
   `search_text` schema,
3. failure to recover from rejected tool calls,
4. failure to initiate repository inspection for conceptual questions.

These should not be collapsed into a generic retrieval failure.

No specialized repository-navigation tool will be introduced until these
failure modes are isolated experimentally.

## Experiment 002 — Scoped Search Interface

The `search_text` interface was extended with an optional workspace-relative
`path` argument. The path is resolved through the existing `Workspace`
authorization boundary before ripgrep executes.

### Result

Deterministic task success changed from **0/9** in the primitive control to
**1/9** in this treatment run.

The more important behavioral change occurred on exact-symbol tasks:

- nav-003: search tool executed
- nav-004: search tool executed
- nav-005: search tool executed and task passed

In the control, comparable `path` arguments were rejected by the original
query-only schema.

The conceptual tasks nav-006 through nav-009 continued to fail with model
protocol errors.

### Decision

Keep scoped search as a Hewn capability.

The change is useful independently of this benchmark, remains constrained by
the workspace authorization boundary, and converted previously invalid search
requests into executable operations.

The single-run improvement from 0/9 to 1/9 is not treated as a general
performance estimate.

The remaining failures require separate investigation rather than additional
changes to the search interface.