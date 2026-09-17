## Module 5 — Context Engineering

### M5-C1 — Production retrieval coverage on Hewn navigation tasks

In the frozen Module 5 production integration configuration, the retrieval and context pipeline included the mechanically expected repository file for all 9 Hewn self-navigation tasks: 5/5 exact-symbol tasks and 4/4 conceptual tasks.

Scope: one Hewn repository snapshot, one nine-task benchmark, BAAI/bge-small-en-v1.5 semantic retrieval, production Module 5 context policy.

Evidence:
- `research/005-context-engineering/results/production-context-run-001.json`

### M5-C2 — End-to-end integration result

In one nine-task integration run with Qwen2.5-Coder-1.5B-Instruct Q4_K_M at temperature 0, the agent completed 1/9 tasks correctly without prepared repository context and 3/9 with the production context pipeline.

The observed difference occurred on exact-symbol tasks: 1/5 without prepared context versus 3/5 with production context. Both conditions scored 0/4 on conceptual tasks.

This is a single-run benchmark result and is not claimed to generalize across repeated trials, repositories, models, or task distributions.

Evidence:
- `research/005-context-engineering/results/production-context-run-001.json`

### M5-C3 — Retrieval success did not imply conceptual-task success

In the same production integration run, all 4 conceptual tasks had expected-file retrieval coverage, but production-context end-to-end success was 0/4.

This demonstrates, for this benchmark configuration, that mechanically retrieving the expected repository evidence was not sufficient for reliable downstream model reasoning and protocol adherence.

Evidence:
- `research/005-context-engineering/results/production-context-run-001.json`