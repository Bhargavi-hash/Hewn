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

## Experiment 003 — Evidence representation

### Question

Given the same retrieved repository evidence identities, how much context
does Hewn require when representing that evidence as structural metadata,
source code, or both?

### Configuration

- Repository: Hewn
- Retrieval architecture: Module 4 hybrid router
- Semantic model: BAAI/bge-small-en-v1.5
- Retrieval representation: symbol documents
- Symbol documents: 138
- Context evidence limit: Top-3 unique files
- Context representations:
  - structure
  - exact symbol source
  - structure + exact symbol source
- Tasks: unchanged nine-task Hewn self-navigation benchmark

Retrieval ranking was held fixed. Representation was applied only after
evidence selection so that this experiment changed context representation,
not retrieval behavior.

### Results

| Representation | Coverage | Avg characters | Avg evidence items |
|---|---:|---:|---:|
| structure | 9/9 (100.0%) | 213.7 | 1.89 |
| source | 9/9 (100.0%) | 2355.4 | 1.89 |
| mixed | 9/9 (100.0%) | 2588.0 | 1.89 |

Relative to structural evidence, whole-symbol source required about
11.0 times as many characters on average. Mixed evidence required about
12.1 times as many.

Expected-file coverage was identical by construction because all three
representations used the same retrieved evidence identities.

### Per-task observation

nav-007 required:

- structure: 487 characters
- source: 6226 characters
- mixed: 6743 characters

This is approximately 12.8 times more text for source and 13.8 times
more for mixed representation compared with structure.

Large source expansion also occurred for exact-symbol retrieval. For
LlamaCppModel, structural evidence required 61 characters while the
whole-symbol source representation required 3855 characters.

### Interpretation

Whole-symbol source code is substantially more expensive than compact
structural evidence in this benchmark.

This does not establish that structural evidence is superior for model
reasoning. Source code contains behavioral information absent from the
structural representation and may justify some or all of its additional
cost.

The result instead shows that whole-symbol source should not be treated
as a free enrichment step, particularly for small-model contexts.

The large variation in symbol body size also suggests that the useful
unit of source context may be smaller than an entire class or other
large symbol body.

### Decision

Retain structural evidence as the compact baseline.

Do not adopt unconditional whole-symbol source or mixed evidence.

Investigate selective source enrichment and smaller source excerpts
before deciding how source code should enter production context.

## Experiment 004 — Model representation ablation

### Question

For the same retrieved repository evidence, does exposing source code instead
of compact structural evidence improve the ability of a small coding model to
answer repository questions enough to justify the additional context?

### Configuration

- Coding model: Qwen2.5-Coder-1.5B-Instruct Q4_K_M
- Inference: llama.cpp
- Temperature: 0.0
- Context window: 4096 tokens
- CPU threads: 4
- Tools exposed: 0
- Retrieval: Module 4 hybrid router
- Evidence limit: top 3 unique files
- Embedding model: BAAI/bge-small-en-v1.5
- Tasks: 9 Hewn self-navigation tasks
- Representations:
  - `structure`: compact structural symbol document
  - `source`: complete source span of the retrieved symbol
  - `mixed`: structural document plus complete source span
- Planned model calls: 27
- Scoring: final response must contain both the expected file and canonical
  symbol.
- Protocol failures are recorded separately from model/infrastructure errors.

### Results

| Representation | Correct | Final responses | Protocol errors | Model errors | Avg context chars | Avg response time |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Structure | 3/9 (33.3%) | 5/9 | 4 | 0 | 343.0 | 6.75 s |
| Source | 4/9 (44.4%) | 6/9 | 3 | 0 | 2484.8 | 15.23 s |
| Mixed | 5/9 (55.6%) | 9/9 | 0 | 0 | 2717.3 | 15.76 s |

### Per-task results

| Task | Route | Structure | Source | Mixed |
| --- | --- | --- | --- | --- |
| nav-001 | exact symbol | PASS | FAIL | FAIL |
| nav-002 | exact symbol | FAIL | PASS | FAIL |
| nav-003 | exact symbol | PASS | PASS | PASS |
| nav-004 | exact symbol | PASS | PASS | PASS |
| nav-005 | exact symbol | FAIL | FAIL | FAIL |
| nav-006 | semantic | protocol error | PASS | PASS |
| nav-007 | semantic | protocol error | protocol error | FAIL |
| nav-008 | semantic | protocol error | protocol error | PASS |
| nav-009 | semantic | protocol error | protocol error | PASS |

### Exact-symbol subset

For the five exact-symbol tasks:

- Structure: 3/5
- Source: 3/5
- Mixed: 2/5

Additional source was therefore not uniformly useful when deterministic
retrieval had already resolved the relevant symbol.

For example, nav-001 changed from a correct structural answer with 114
characters of context to incorrect source and mixed answers with 987 and
1053 characters respectively.

nav-005 failed under all three representations even though source and mixed
expanded the context from 124 characters to approximately 4000 characters.

### Conceptual subset

For the four semantic/conceptual tasks:

- Structure: 0/4, with 4 protocol errors
- Source: 1/4, with 3 protocol errors
- Mixed: 3/4, with 0 protocol errors

The conceptual subset therefore showed a different pattern from the
exact-symbol subset. Richer evidence was associated with both greater task
success and better protocol adherence in this run.

nav-007 remained unresolved. Structure and source produced protocol errors,
while mixed produced a valid final response but selected the wrong file and
symbol.

### Interpretation

This experiment separates retrieval success from evidence usability.

Retrieval covered the expected file for every task, but the coding model's
ability to use that evidence depended on its representation. Correct
retrieval therefore did not guarantee correct repository reasoning.

Compact structural evidence was cheapest, but in this run it did not solve
any of the four conceptual tasks. Whole-symbol source increased context
substantially and solved one conceptual task. Mixed evidence solved three of
four conceptual tasks and produced protocol-valid final responses on all nine
tasks.

However, richer evidence did not improve the exact-symbol subset. This
suggests that a single representation policy may be inappropriate for all
retrieval routes.

Experiment 003 established that whole-symbol source is expensive.
Experiment 004 provides evidence that source information can nevertheless be
useful for conceptual questions. This motivates testing whether the useful
source information can be represented more compactly.

These results apply only to this nine-task Hewn self-navigation benchmark,
model, prompt, retrieval configuration, and single deterministic run. They do
not establish that mixed representation is generally superior.

## Experiment 005 — Source granularity

### Question

Can Hewn preserve the observed usefulness of source-aware context for
conceptual repository questions while exposing substantially less source
code?

### Design

Experiment 004 showed that source-aware representations were most useful
on the conceptual subset of the navigation benchmark. Experiment 005
therefore restricted evaluation to those four tasks:

- nav-006
- nav-007
- nav-008
- nav-009

The following variables were held fixed:

- retrieval: Module 4 hybrid retrieval
- embedding model: `BAAI/bge-small-en-v1.5`
- coding model: `Qwen2.5-Coder-1.5B-Instruct Q4_K_M`
- evidence selection: top 3 unique files
- temperature: 0
- tools exposed: none
- prompt and scoring procedure
- repository and task definitions

Three source representations were compared:

1. `signature` — symbol signature only
2. `bounded_source` — signature plus complete AST statements, with an
   800-character per-symbol target
3. `whole_source` — the complete retrieved symbol source

The bounded representation preserved complete AST statement boundaries
rather than truncating source at an arbitrary character position.

Total model calls: 12.

### Results

| Representation | Success | Final responses | Protocol errors | Avg context chars | Avg response time |
| --- | ---: | ---: | ---: | ---: | ---: |
| Signature | 0/4 | 0/4 | 4 | 442.0 | 11.07 s |
| Bounded source | 2/4 | 2/4 | 2 | 1747.2 | 16.22 s |
| Whole source | 2/4 | 2/4 | 2 | 3770.8 | 11.42 s |

All four tasks had the expected file represented in the selected
retrieval evidence.

Per-task behavior differed despite the aggregate tie:

- nav-006: bounded source and whole source both succeeded.
- nav-007: all three representations produced protocol failures.
- nav-008: whole source succeeded while bounded source produced a
  protocol failure.
- nav-009: bounded source succeeded while whole source produced a
  protocol failure.

Bounded source used approximately 53.7% fewer context characters than
whole source on average while matching its aggregate 2/4 success count.

The context reduction did not translate into lower measured response
latency: bounded source averaged 16.22 seconds compared with 11.42
seconds for whole source.

### Interpretation

This four-task follow-up does not establish that bounded source is
equivalent or superior to whole source.

It does show that the full source volume was not necessary to obtain the
same aggregate success count in this run. However, bounded and whole
source succeeded on different tasks, showing that source selection can
change model behavior rather than merely reduce prompt size.

Signature-only evidence produced protocol failures on all four
conceptual tasks in this configuration. This suggests that signatures
alone were insufficient for reliable conceptual reasoning by this
1.5B-parameter model on this subset.

The opposing outcomes on nav-008 and nav-009 also argue against treating
source volume as a monotonic quality control: additional source may help
one query while hurting another.

The next context-engineering question should therefore focus on which
evidence is presented and how it is organized, rather than tuning the
800-character threshold against this small benchmark.

## Experiment 006 — Evidence position

### Question

Holding retrieved evidence, representation, and total context size fixed,
does the position of relevant evidence affect a small coding model's
behavior on conceptual repository questions?

### Design

The experiment used the four conceptual navigation tasks from
Experiment 005:

- nav-006
- nav-007
- nav-008
- nav-009

Retrieval was fixed to the Module 4 hybrid retriever with the top three
unique files. Evidence representation was fixed to the 800-character
bounded-source representation from Experiment 005.

Three ordering conditions were compared:

1. `retrieval_order` — preserve semantic retrieval order.
2. `relevant_first` — move the benchmark-expected file to position 1.
3. `relevant_last` — move the benchmark-expected file to the final
   position.

The latter two conditions use benchmark labels and are diagnostic only.
They are not valid production ordering algorithms.

Evidence content and total context size were unchanged across ordering
conditions within each task.

Total model calls: 12.

### Results

| Ordering | Success | Final responses | Protocol errors | Avg context chars | Avg response time |
| --- | ---: | ---: | ---: | ---: | ---: |
| Retrieval order | 3/4 | 4/4 | 0 | 1747.2 | 7.20 s |
| Relevant first | 3/4 | 3/4 | 1 | 1747.2 | 9.58 s |
| Relevant last | 1/4 | 3/4 | 1 | 1747.2 | 14.08 s |

Per-task outcomes:

- nav-006: all three orderings succeeded.
- nav-007: retrieval order and relevant-last returned incorrect final
  answers; relevant-first produced a protocol error.
- nav-008: relevant evidence at position 1 succeeded; moving it to
  position 3 produced a protocol error.
- nav-009: relevant evidence at position 1 succeeded; moving it to
  position 3 produced an incorrect final answer.

The average context size was identical across all three conditions.

### Interpretation

Evidence position affected model behavior in this four-task diagnostic
even though evidence content and total context size were held constant.

The strongest negative intervention was moving the benchmark-relevant
file to the final position: aggregate success decreased from 3/4 under
retrieval order to 1/4 under relevant-last.

This does not establish a universal first-position advantage. Moving the
expected file first did not improve aggregate success over retrieval
order and did not solve nav-007.

The label-aware relevant-first and relevant-last conditions must not be
used as production policies. Their purpose is only to establish whether
position can matter.

The bounded-source retrieval-order condition also differed from its
nominally equivalent condition in Experiment 005. Experiment 005
produced 2/4 successes and two protocol errors, while Experiment 006
produced 3/4 successes and no protocol errors. Therefore single-run
results should not be treated as deterministic estimates of model
quality, even at temperature 0.

The experiment motivates studying a legitimate, label-free evidence
ordering policy rather than assuming retrieval rank alone is the final
context order.

## Experiment 007 — Dependency-aware evidence ordering

### Question

Can deterministic repository dependency structure improve the ordering of
already-selected evidence without using benchmark labels?

### Design

Experiment 006 established that evidence position can affect model
behavior. Experiment 007 therefore tested two deployable, label-free
ordering policies based on the internal file dependency graph created in
Module 3.

`FileDependency(source=A, target=B)` means that A imports or depends on B.

The three conditions were:

1. `retrieval_order` — preserve semantic retrieval order.
2. `dependency_first` — prioritize selected files that other selected
   files depend on.
3. `dependent_first` — prioritize selected files that depend on other
   selected files.

Ties preserved original retrieval order.

Only dependency relationships among the three selected files were used.

The following remained fixed:

- four conceptual tasks: nav-006 through nav-009
- Module 4 hybrid retrieval
- top 3 unique files
- 800-character bounded-source representation
- Qwen2.5-Coder-1.5B-Instruct Q4_K_M
- temperature 0
- no tools
- prompt and scoring
- evidence content and total context size

Total model calls: 12.

### Treatment exposure

The selected evidence contained dependency relationships for every task:

- nav-006: 1 selected dependency
- nav-007: 1 selected dependency
- nav-008: 3 selected dependencies
- nav-009: 3 selected dependencies

`dependency_first` changed the evidence order on 4/4 tasks.

`dependent_first` changed the evidence order on 3/4 tasks.

The experiment therefore had substantial treatment exposure.

### Results

| Ordering | Success | Final responses | Protocol errors | Order changes | Avg context chars | Avg response time |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Retrieval order | 3/4 | 4/4 | 0 | 0/4 | 1747.2 | 7.05 s |
| Dependency first | 0/4 | 0/4 | 4 | 4/4 | 1747.2 | 14.85 s |
| Dependent first | 2/4 | 2/4 | 2 | 3/4 | 1747.2 | 11.20 s |

Dependency-first changed all four contexts and produced protocol failures
on all four tasks.

Dependent-first changed three contexts. Among those three changed cases,
one succeeded and two produced protocol failures. Its fourth success,
nav-009, occurred without changing retrieval order.

### Interpretation

The result does not support replacing semantic retrieval order with
either tested dependency-based ordering policy.

In this four-task run, dependency-first consistently changed context
ordering but produced no valid final responses. Dependent-first also did
not improve over retrieval order.

This does not imply that repository dependencies are harmful or useless.
The dependency graph represents architectural relationships, while
semantic retrieval rank represents query-relative relevance. Those are
different signals.

The experiment suggests that blindly replacing query-relative ranking
with repository-topology ordering can remove useful information encoded
in the retrieval ranking.

The current evidence therefore supports retaining semantic retrieval
order as Hewn's default context order while using dependency structure
for other repository-intelligence purposes unless future experiments
show a better query-aware combination.

## Experiment 008 — Evidence diversity

### Question

When selecting three semantic retrieval results, does forcing file-level
diversity improve small-model reasoning compared with taking the raw
top-three symbol results?

### Design

Two selection policies were compared:

1. `raw_top3` — take the first three retrieved symbol documents,
   allowing multiple symbols from the same file.
2. `unique_file_top3` — preserve retrieval order while selecting at most
   one symbol from each file.

The following remained fixed:

- conceptual tasks nav-006 through nav-009
- Module 4 hybrid retrieval
- evidence limit of three
- semantic retrieval order
- 800-character bounded-source representation
- Qwen2.5-Coder-1.5B-Instruct Q4_K_M
- temperature 0
- no tools
- prompt and scoring

Total model calls: 8.

### Treatment exposure

The two policies selected different evidence on 2/4 tasks:

- nav-006: raw Top-3 contained evidence from one file; unique-file Top-3
  contained evidence from three files.
- nav-009: raw Top-3 contained evidence from one file; unique-file Top-3
  contained evidence from three files.

The selections were identical on nav-007 and nav-008.

Therefore, causal interpretation of the diversity intervention should
focus on nav-006 and nav-009.

### Results

| Policy | Success | Final responses | Protocol errors | Avg unique files | Avg context chars | Avg response time |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Raw Top-3 | 1/4 | 2/4 | 2 | 2.00 | 1584.2 | 9.85 s |
| Unique-file Top-3 | 3/4 | 4/4 | 0 | 3.00 | 1747.2 | 9.62 s |

Task-level results:

- nav-006: selection changed; both policies succeeded.
- nav-007: selection did not change; both policies failed.
- nav-008: selection did not change; raw Top-3 produced a protocol error
  while unique-file Top-3 succeeded.
- nav-009: selection changed; raw Top-3 produced a protocol error while
  unique-file Top-3 succeeded.

### Interpretation

The aggregate 1/4 versus 3/4 difference must not be attributed entirely
to file diversity.

On nav-008, the two policies supplied identical selected evidence and
identical context size, yet produced different model outcomes. This is
additional evidence of run-to-run variation in the current small-model
evaluation setup.

Among the two tasks where selection actually changed, unique-file
selection did not hurt either task: nav-006 succeeded under both
conditions, while nav-009 succeeded only under unique-file selection.

This provides limited positive evidence for retaining file-level
deduplication as a default selection policy, particularly because it
prevents the context from being dominated by several retrieved symbols
from one file. It does not establish that file diversity generally
improves model success.

The experiment also reinforces the need for repeated trials in the later
evaluation module.

## Production integration evaluation

After the isolated context experiments, the surviving Module 5 policies were integrated into the production path through `ContextPolicy`, `ContextBuilder`, and `HewnSession`.

The production policy was frozen before the final integration evaluation:

- exact-symbol retrieval keeps the single compact structural result;
- semantic retrieval preserves semantic ranking;
- semantic context selects the first 3 unique files;
- semantic symbols use bounded source with an 800-character per-symbol limit;
- dependency-aware reordering is not applied;
- character-budget skip-to-fit packing is not applied;
- semantic retrieval requests up to 12 candidates so file-level deduplication has room to select 3 distinct files.

The 12-candidate retrieval limit is an engineering default, not an experimentally established optimum.

### Evaluation design

The final integration evaluation compared two conditions on the 9 existing Hewn self-navigation tasks:

1. `no_context` — the normal agent receives only the task.
2. `production_context` — the same agent receives context prepared by the production retrieval and context-building pipeline.

Both conditions used:

- Qwen2.5-Coder-1.5B-Instruct Q4_K_M;
- temperature 0.0;
- the normal builtin Hewn tool registry;
- the same task set and mechanical file-and-symbol correctness criterion;
- one run per task and condition.

Condition execution order was alternated by task to avoid making treatment condition identical to execution order.

This does not eliminate generation instability. Repeated-trial evaluation is deferred to Module 11.

### Results

Production retrieval covered the expected file for all 9 tasks:

- exact-symbol routes: 5/5 expected files covered;
- semantic routes: 4/4 expected files covered;
- overall retrieval coverage: 9/9.

End-to-end agent results were:

| Metric | No context | Production context |
| --- | ---: | ---: |
| Correct | 1/9 | 3/9 |
| Final responses | 3/9 | 6/9 |
| Exact-symbol success | 1/5 | 3/5 |
| Conceptual success | 0/4 | 0/4 |
| Model errors | 2 | 0 |
| Protocol errors | 4 | 3 |
| Average context characters | 0.0 | 739.1 |
| Average response time | 16.00 s | 11.55 s |

For runs where agent metrics were available, the reported averages were:

| Metric | No context | Production context |
| --- | ---: | ---: |
| Model calls | 1.67 | 1.17 |
| Tool calls | 0.67 | 0.17 |

These model-call and tool-call averages exclude runs where a model or protocol error occurred before complete agent metrics were returned, so they should not be interpreted as clean population-wide reductions.

The no-context response-time mean was also strongly affected by a 92.62-second `nav-004` run. No latency improvement is claimed from this experiment.

### Exact-symbol behavior

Production context succeeded on `nav-001`, `nav-002`, and `nav-005` using only 56–61 characters of compact structural evidence and no tool calls.

This supports retaining the exact-symbol policy of supplying one compact deterministic result without source expansion or filler.

However, `nav-003` and `nav-004` still failed despite expected-file retrieval coverage. Correct compact evidence therefore did not guarantee correct use of that evidence by the coding model.

### Conceptual behavior

All four conceptual tasks had expected-file retrieval coverage, but none produced a correct end-to-end answer under the production-context condition.

`nav-007` produced a valid but incorrect final response despite receiving context that covered the expected file.

`nav-006`, `nav-008`, and `nav-009` failed at the model protocol boundary despite expected-file retrieval coverage.

The final integration run therefore separates two failure classes:

1. repository evidence acquisition; and
2. downstream model interpretation, protocol adherence, and action selection.

On this benchmark, the production retrieval/context pipeline succeeded at the first for all 9 tasks, while conceptual-task failures remained in the second.

### Interpretation

In this single nine-task Hewn self-navigation integration run, production context was associated with higher end-to-end success than no prepared context, from 1/9 to 3/9.

The observed gain occurred entirely on exact-symbol tasks, which changed from 1/5 to 3/5. Conceptual tasks remained 0/4 despite 4/4 expected-file retrieval coverage.

This experiment does not establish that context engineering generally improves coding-agent accuracy, nor that the observed aggregate difference is stable across repeated runs, repositories, models, or task distributions.

The strongest conclusion is narrower: Hewn can now mechanically place the expected repository file into the model context for all tasks in this benchmark, but correct evidence is not sufficient for reliable reasoning by the current 1.5B local model.