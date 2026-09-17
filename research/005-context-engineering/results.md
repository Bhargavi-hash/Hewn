# Results - Module 5: Context Engineering

## Experiment 001 — Fixed evidence-count budgets

### Question

How does the number of retrieved evidence items affect expected-file
coverage and context size?

### Configuration

- Repository: Hewn
- Retrieval architecture: Module 4 hybrid router
- Semantic model: BAAI/bge-small-en-v1.5
- Representation: symbol documents
- Symbol documents: 133
- Evidence-count budgets: 1, 3, 5, all
- Tasks: unchanged nine-task Hewn self-navigation benchmark

Retrieved semantic results were collapsed to unique source files before
context budgeting. Exact-symbol routes naturally contained only one
evidence item.

### Results

| Budget | Coverage | Avg characters | Avg evidence items | Avg unique files |
|---|---:|---:|---:|---:|
| 1 | 8/9 (88.9%) | 90.7 | 1.00 | 1.00 |
| 3 | 9/9 (100.0%) | 213.7 | 1.89 | 1.89 |
| 5 | 9/9 (100.0%) | 361.9 | 2.78 | 2.78 |
| all | 9/9 (100.0%) | 2007.4 | 13.44 | 13.44 |

The exact-symbol tasks nav-001 through nav-005 required only one
evidence item regardless of the maximum budget.

Among the conceptual tasks, nav-007 was the only task not covered by
the Top-1 context. Its expected completion.py file was included by the
Top-3 budget.

### Observation

Increasing the evidence budget from one to three recovered the remaining
expected file and increased benchmark coverage from 8/9 to 9/9.

Increasing the budget beyond three did not improve expected-file
coverage in this benchmark.

The all-evidence condition averaged 2007.4 characters compared with
213.7 characters for the Top-3 condition, approximately 9.4 times as
much retrieved text, while both achieved 9/9 expected-file coverage.

This establishes a mechanical coverage/context-size frontier. It does
not establish that Top-3 is the best context for a language model,
because additional evidence may affect reasoning even when expected-file
coverage remains unchanged.

### Decision

Keep evidence-count selection as a context-policy primitive.

Do not select a production evidence-count budget from this experiment
alone.

Next test explicit character budgets, where evidence size rather than
item count constrains context construction.

## Experiment 002 — Character-budget packing

### Question

How does an explicit character budget affect expected-file coverage and
context size compared with a fixed evidence-count budget?

### Configuration

- Repository: Hewn
- Retrieval architecture: Module 4 hybrid router
- Semantic model: BAAI/bge-small-en-v1.5
- Representation: symbol documents
- Symbol documents: 134
- Character budgets: 100, 200, 400, 800, unlimited
- Atomic evidence policy: always retain the highest-ranked item, then
  skip later items that do not fit while continuing to consider lower
  ranked evidence
- Tasks: unchanged nine-task Hewn self-navigation benchmark

### Results

| Budget | Coverage | Avg characters | Avg evidence items | Over-budget tasks |
|---|---:|---:|---:|---:|
| 100 | 8/9 (88.9%) | 90.7 | 1.00 | 3 |
| 200 | 8/9 (88.9%) | 112.0 | 1.22 | 0 |
| 400 | 8/9 (88.9%) | 200.3 | 1.89 | 0 |
| 800 | 9/9 (100.0%) | 375.8 | 3.11 | 0 |
| unlimited | 9/9 (100.0%) | 2095.9 | 13.89 | 0 |

At a 100-character budget, three tasks exceeded the nominal budget
because the highest-ranked atomic evidence item was larger than the
budget. The policy intentionally retained that first item.

nav-007 was the only coverage failure from 100 through 400 characters.
Its expected completion.py evidence was not retained until the
800-character condition.

### Comparison with evidence-count budgeting

Experiment 001's Top-3 condition achieved 9/9 expected-file coverage
with 213.7 average characters.

The 400-character packing condition averaged a similar 200.3 characters
but achieved only 8/9 coverage.

This demonstrates that average context size does not determine evidence
coverage. The packing policy can skip a higher-ranked evidence item that
does not fit and admit smaller lower-ranked items instead.

Therefore, fixed evidence count and character-budget packing encode
different context-selection policies rather than merely different ways
of expressing the same limit.

### Atomic evidence observation

The 100-character condition exceeded its nominal budget for three tasks.

This exposes a limitation of whole-item context construction: strict
budgets cannot always be respected when individual evidence units are
larger than the available budget.

Potential solutions include smaller evidence representations or
controlled truncation, but neither is introduced in this experiment.

### Decision

Keep explicit context-cost budgeting as a useful primitive, but do not
adopt the current skip-to-fit character packing policy as the production
context policy.

Preserving high-ranked evidence and controlling representation size
should be investigated before selecting a final budget policy.