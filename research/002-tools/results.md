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

## Experiment 003 — Semantic Symbol Lookup

A deterministic Python AST-backed `find_symbol` tool was added alongside the
existing primitive tools.

The tool maps an exact symbol name to class or function definitions rather
than returning every textual occurrence of that name.

### Result

Deterministic task success:

| Configuration | Success |
|---|---:|
| Primitive Module 1 tools | 0/9 |
| Scoped search | 1/9 |
| Scoped search + `find_symbol` | 3/9 |

The three successful tasks in Experiment 003 were:

- nav-001 — `ToolExecutor`
- nav-003 — `CompletionPolicy`
- nav-005 — `LlamaCppModel`

Each completed with two model calls and one tool call.

Two other exact-symbol tasks, nav-002 and nav-004, failed without making any
tool call. Therefore `find_symbol` does not by itself solve the model's
premature-answer behavior.

All four conceptual-navigation tasks also failed. Three terminated with model
protocol errors, while nav-006 returned without using a tool.

### Interpretation

The experiment provides narrow engineering evidence that semantic tool design
can reduce reasoning burden for exact-symbol repository navigation.

`find_symbol` moves definition identification out of the model:

    text search
        -> many references
        -> model identifies definition

becomes:

    find_symbol
        -> deterministic AST analysis
        -> definition locations

The result does not establish a general 3x performance improvement. Each
configuration currently has only one benchmark run, and the task set is small
and drawn from Hewn itself.

The remaining conceptual failures indicate a different problem: the model must
first map a behavioral description to relevant repository concepts before an
exact-symbol tool becomes useful.

### Decision

Keep `find_symbol`.

Do not add further specialized navigation tools in Module 2. The unresolved
conceptual-navigation problem becomes an input to Module 3, which will build
repository structure and symbol intelligence systematically.