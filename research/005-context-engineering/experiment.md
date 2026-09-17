# Module 5 Experiment Plan

## Controlled variables

Unless explicitly changed by an experiment:

- repository: Hewn
- retrieval architecture: Module 4 hybrid router
- semantic model: BAAI/bge-small-en-v1.5
- semantic representation: symbol documents
- task set: existing nine self-navigation tasks
- repository index: Module 4 implementation

The retrieval policy remains fixed while context construction changes.

## Metrics

Structural metrics:

- context characters
- evidence items
- expected-file coverage
- duplicate-file count
- unique-file count

Runtime metrics:

- context construction time
- retrieval time

End-to-end metrics:

- model calls
- tool calls
- task success
- protocol failures
- unsupported guesses
- wall time

## Experiment 001 — Evidence-count budgets

Compare:

- Top-1
- Top-3
- Top-5
- all retrieved evidence

Question:

How much additional evidence is retained as the fixed item budget grows?

This experiment does not yet measure model intelligence. It establishes
the mechanical cost/coverage frontier produced by evidence-count budgets.

## Experiment 002 — Character budgets

Compare fixed character budgets while preserving ranked evidence order.

Candidate budgets:

- 500
- 1000
- 2000
- unlimited

Question:

Can Hewn enforce an explicit context budget without accidentally dropping
the highest-value evidence?

## Experiment 003 — Evidence representation

Compare:

- structural symbol metadata
- source excerpts
- mixed structural + source evidence

Question:

Does richer evidence justify its context cost?

## Experiment 004 — Evidence ordering

Evaluate whether ordering retrieved evidence changes model behavior.

## Experiment 005 — Evidence diversity

Evaluate deterministic duplicate and near-duplicate suppression.

## Experiment 006 — End-to-end small-model evaluation

Run the fixed context policies through Hewn's local coding model.

This experiment determines whether mechanical context improvements
translate into model-task improvements.