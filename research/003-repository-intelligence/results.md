# Results

## Experiment 001 — Model-Selected Repository Map

Tool configuration:

- existing primitive tools
- `find_symbol`
- `repository_map`

Result: **0/9 tasks passed**.

### Exact-symbol tasks

nav-001 through nav-005 each terminated after one model call and zero
tool calls.

The model produced unsupported repository-path guesses rather than
selecting either `find_symbol` or `repository_map`.

Examples included invented locations such as:

- `src/tool_executor.py`
- `src/completion/CompletionPolicy.py`
- `src/agent_metrics.py`

### Conceptual tasks

nav-006 through nav-009 terminated with `ModelProtocolError`.

The raw responses were Markdown-fenced JSON final responses rather than
tool requests. Their contents also contained unsupported architectural
claims, including invented symbols and files.

Therefore, protocol formatting was not the only failure: accepting the
JSON after removing its Markdown fences would still have accepted
ungrounded answers.

### Observation

`repository_map` was invoked zero times across all nine tasks.

Experiment 001 therefore does not establish whether the structural
repository representation helps downstream reasoning. It establishes
that, under this configuration and run, exposing the structural map as
an additional model-selected tool was insufficient to cause the model
to inspect the repository.

### Next experiment

Supply deterministic structural repository context before the model's
first decision while otherwise preserving the benchmark configuration.

This separates:

1. usefulness of structural repository knowledge, from
2. the model's ability to select the tool that exposes that knowledge.