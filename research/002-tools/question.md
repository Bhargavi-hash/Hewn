# Module 2 — Tools Are Part of Intelligence

## Research Question

Can semantically appropriate repository tools reduce the reasoning burden
on a small coding model and improve coding-agent performance compared with
a minimal primitive tool vocabulary?

## Primary Hypothesis

For repository tasks that otherwise require multiple primitive search and
inspection operations, a semantic tool can reduce model calls and tool calls
while maintaining or improving task success.

## Competing Hypothesis

Adding specialized tools increases action-selection complexity. For a small
model, this additional choice may offset or exceed the reasoning saved by the
specialized operation.

## Experimental Principle

Do not introduce a specialized tool merely because it appears useful.

First identify a repeated limitation in traces produced with the primitive
Module 1 tool vocabulary. Then introduce the smallest tool that directly
addresses that observed limitation and rerun the same tasks.

## Control

Module 1 TinyHewn tool vocabulary:

- `list_directory`
- `read_file`
- `search_text`
- `replace_text`
- `run_check`

## Initial Measurements

For each task record:

- task success
- model calls
- tool calls
- successful and failed tool calls
- protocol failures
- files inspected where measurable
- wall-clock time
- final answer correctness
- observed failure mode

## Constraints

- Keep the model fixed during a tool-ablation comparison.
- Keep inference parameters fixed.
- Keep the system prompt fixed.
- Keep task wording fixed.
- Change one tool-related variable at a time.
- Preserve failed experiments.
- Do not add semantic tools until primitive-tool traces justify them.