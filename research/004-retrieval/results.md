# Results

## Experiment 001 — Lexical overlap baseline

Repository documents contained:

- repository-relative file path
- symbol names and qualified names
- internal file dependencies

The retriever used normalized unique-token overlap between the query and
each repository document.

### Results

| Metric | Result |
| --- | ---: |
| Tasks | 9 |
| Documents | 24 |
| Top-1 | 1/9 |
| Top-3 | 2/9 |

The only Top-1 success was nav-009.

CompletionPolicy in nav-003 was retrieved at rank 2 and therefore passed
Top-3.

### Expected-file ranks

| Task | Category | Expected rank |
| --- | --- | ---: |
| nav-001 | symbol | 10 |
| nav-002 | symbol | 14 |
| nav-003 | symbol | 2 |
| nav-004 | symbol | 10 |
| nav-005 | symbol | 6 |
| nav-006 | concept | 14 |
| nav-007 | concept | 12 |
| nav-008 | concept | 23 |
| nav-009 | concept | 1 |

### Observation 1 — Equal token weighting is weak

Exact symbol names did not reliably dominate common repository vocabulary.

For example, nav-001 explicitly names `ToolExecutor`, but the expected
`src/hewn/tools.py` document ranked tenth.

The lexical scorer gives every unique overlapping query token equal
weight. A rare identifier such as `ToolExecutor` therefore receives no
more importance than common repository terms.

This motivates an experiment with corpus-aware term weighting.

### Observation 2 — Ranking and representation are separate problems

The conceptual failures reveal a second limitation.

Repository documents currently contain structural facts such as paths,
symbols and dependencies. They do not contain source-level behavioral
evidence.

A query such as "preventing repository file operations from escaping the
configured workspace" describes behavior rather than naming an
identifier. The structural document for `workspace.py` may therefore
contain insufficient lexical evidence for the query.

Improving the ranking algorithm cannot recover information absent from
the retrieval representation.

### Decision

Keep this lexical implementation unchanged as the primitive retrieval
baseline.

The next experiment will apply BM25-style corpus-aware term weighting to
the same repository documents.

This changes the ranking method while holding the document representation
constant.

Only after measuring that result will the experiment change the document
representation.

## Experiment 003 — BM25 with signature-enriched documents

### Change

The BM25 ranking algorithm, tokenizer, task set, and repository scope were
held constant.

Repository documents were enriched with deterministic function and method
signatures extracted from the Python AST.

### Results

| Representation | Top-1 | Top-3 | Avg Top-1 chars | Avg Top-3 chars |
|---|---:|---:|---:|---:|
| Structural documents | 4/9 | 6/9 | 309.4 | 854.7 |
| Structural documents + signatures | 2/9 | 4/9 | 538.6 | 1991.3 |

Expected-file rank changes:

| Task | Structural | + Signatures |
|---|---:|---:|
| nav-001 | 1 | 2 |
| nav-002 | 3 | 5 |
| nav-003 | 1 | 1 |
| nav-004 | 1 | 4 |
| nav-005 | 1 | 1 |
| nav-006 | 4 | 5 |
| nav-007 | 12 | 12 |
| nav-008 | 24 | 13 |
| nav-009 | 2 | 3 |

### Interpretation

Signature enrichment did not improve retrieval overall in this nine-task
Hewn self-navigation benchmark.

The representation increased the average Top-3 context from 854.7 to
1991.3 characters while Top-3 retrieval decreased from 6/9 to 4/9.

The strongest positive movement occurred on nav-008, where the expected
tools.py file moved from rank 24 to rank 13. The added
ToolExecutor.execute signature therefore supplied useful task-relevant
vocabulary, but that local improvement was outweighed by additional
tokens and changed corpus statistics across the remaining documents.

This experiment demonstrates that adding valid structural information
indiscriminately does not necessarily improve retrieval. Representation
content and retrieval granularity must be evaluated separately.

### Decision

Do not use signature-enriched file documents as the default retrieval
representation based on this result.

The next experiment will hold BM25 and the tokenizer constant while
changing the retrieval unit from source files to individual symbols.

## Experiment 004 — Symbol-level BM25 retrieval

### Change

The BM25 ranking algorithm, tokenizer, task set, repository scope, and
AST-derived repository information were held constant.

The retrieval unit changed from one document per source file to one
document per symbol.

Symbol results were collapsed to unique source files for Top-K file
evaluation, preserving the highest-ranked symbol for each file.

### Corpus

- File documents: 26
- Symbol documents: 108

### Results

| Representation | Top-1 | Top-3 | Avg Top-1 chars | Avg Top-3 chars |
|---|---:|---:|---:|---:|
| Signature-enriched file | 2/9 | 4/9 | 538.6 | 1991.3 |
| Symbol-level | 0/9 | 5/9 | 166.6 | 462.6 |

Expected-file rank under symbol retrieval:

| Task | Rank |
|---|---:|
| nav-001 | 3 |
| nav-002 | 4 |
| nav-003 | 3 |
| nav-004 | 3 |
| nav-005 | 3 |
| nav-006 | 5 |
| nav-007 | 11 |
| nav-008 | 12 |
| nav-009 | 2 |

### Interpretation

Symbol-level retrieval substantially reduced the amount of retrieved
text, but it did not improve Top-1 accuracy in this nine-task Hewn
self-navigation benchmark.

Top-3 accuracy improved from 4/9 to 5/9 relative to signature-enriched
file documents while average Top-3 context decreased from 1991.3 to
462.6 characters.

The retrieved symbols were often lexically plausible but represented a
different architectural responsibility from the expected target. For
example, parsing a tool call is distinct from executing it, and parsing
a final response is distinct from deciding whether completion is
allowed.

The exact-symbol tasks also exposed a separate issue: query vocabulary
such as "find" and "symbol" strongly favored repository search helpers
even when the query explicitly contained the target identifier.

### Decision

Do not use symbol-level BM25 as a universal repository retriever.

Preserve symbol-level documents because they provide compact retrieval
units.

Separate exact identifier resolution from conceptual retrieval.
Explicit identifiers should use deterministic repository indexes when
possible. Conceptual queries require a retrieval method capable of
matching behavioral meaning rather than token overlap.

## Experiment 005 — Local semantic symbol retrieval

### Question

Can a small local embedding model distinguish behavioral repository
responsibilities that lexical BM25 confuses?

### Configuration

- Model: BAAI/bge-small-en-v1.5
- Embedding dimension: 384
- Retrieval representation: symbol-level structural documents
- Symbol documents: 120
- Ranking: normalized embedding similarity
- Tasks: unchanged nine-task Hewn self-navigation benchmark

The repository corpus was embedded once. Each benchmark query was then
embedded independently and ranked against the precomputed corpus.

### Results

| Metric | Result |
|---|---:|
| Top-1 | 8/9 (88.9%) |
| Top-3 | 9/9 (100.0%) |
| Average Top-1 context | 90.7 chars |
| Average Top-3 context | 421.9 chars |
| Model load | 4.667 s |
| Corpus indexing | 15.250 s |
| Average query time | 0.0448 s |

Expected-file ranks:

| Task | Rank |
|---|---:|
| nav-001 | 1 |
| nav-002 | 1 |
| nav-003 | 1 |
| nav-004 | 1 |
| nav-005 | 1 |
| nav-006 | 1 |
| nav-007 | 3 |
| nav-008 | 1 |
| nav-009 | 1 |

### Comparison with symbol BM25

Using symbol-level documents, BM25 achieved 0/9 Top-1 and 5/9 Top-3.
Semantic retrieval achieved 8/9 Top-1 and 9/9 Top-3 in this benchmark
configuration.

Average Top-3 context also decreased from 462.6 characters under
symbol BM25 to 421.9 characters under semantic retrieval.

The result is evidence that semantic ranking addresses failure modes
that token-overlap ranking could not resolve in this task set. It is
not evidence that semantic retrieval universally outperforms BM25
across repositories or coding tasks.

### Behavioral observations

For nav-008, BM25 ranked the expected tools.py file at 12. Semantic
retrieval ranked ToolExecutor.execute first, ahead of
_parse_tool_call. This is consistent with semantic retrieval better
distinguishing tool execution from tool-call parsing.

For nav-006, workspace.py moved from rank 5 under symbol BM25 to rank
1 under semantic retrieval.

For nav-009, LlamaCppModel.respond ranked first, ahead of generic
model-response parsing symbols.

nav-007 remained unresolved at Top-1. _parse_final_response ranked
first, Agent.run second, and CompletionPolicy.rejection_reason third.
This suggests that embedding similarity alone does not always
distinguish parsing, orchestration, and authorization responsibilities
when symbol documents contain little behavioral description.

### Decision

Keep semantic symbol retrieval as a strong candidate for conceptual
repository retrieval.

Do not tune the representation specifically for nav-007.

Next evaluate a hybrid retrieval policy that uses deterministic symbol
resolution for explicit identifiers and semantic retrieval for
conceptual queries.