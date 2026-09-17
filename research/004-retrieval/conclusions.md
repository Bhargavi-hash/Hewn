# Module 4 Conclusions — Retrieval Without Wasting Context

## Research question

Can Hewn retrieve a small, relevant subset of repository knowledge
instead of placing a complete repository map into the model context?

## What we tested

Module 4 progressed through six controlled experiments:

1. lexical file retrieval,
2. BM25 file retrieval,
3. signature-enriched file retrieval,
4. symbol-level BM25 retrieval,
5. local semantic symbol retrieval,
6. deterministic exact-symbol routing with semantic fallback.

The same nine Hewn self-navigation tasks were retained throughout the
module. The benchmark is intentionally small and repository-specific,
so conclusions are limited to this configuration.

## Main findings

### 1. Simple lexical overlap was insufficient

Lexical retrieval achieved 1/9 Top-1 and 2/9 Top-3 in the matched
25-document run.

Equal token weighting allowed common repository vocabulary to compete
with much more informative identifiers.

### 2. Corpus-aware lexical weighting helped

BM25 over the same structural file documents improved retrieval to
4/9 Top-1 and 6/9 Top-3.

This demonstrated that ranking quality mattered independently of the
repository representation.

### 3. More information was not automatically better information

Adding function and method signatures to every file document reduced
performance to 2/9 Top-1 and 4/9 Top-3 while substantially increasing
retrieved context.

The signatures were retained as repository knowledge, but the experiment
rejected indiscriminately placing them into every file-level retrieval
document.

This established an important architectural distinction:

Repository knowledge != retrieval representation != model context.

### 4. Smaller retrieval units reduced context but did not solve ranking

Symbol-level BM25 reduced average Top-3 context substantially, but
achieved 0/9 Top-1 and 5/9 Top-3.

The retrieved symbols were frequently lexically related to the query
without owning the expected architectural responsibility.

### 5. Semantic retrieval addressed several lexical failure modes

Using BAAI/bge-small-en-v1.5 over symbol documents achieved 8/9 Top-1
and 9/9 Top-3.

For example, ToolExecutor.execute ranked ahead of _parse_tool_call for
the task describing conversion of a requested model action into actual
tool execution.

This is evidence, within this benchmark configuration, that semantic
ranking can distinguish behavioral relationships that token overlap
alone did not resolve.

### 6. Deterministic questions should remain deterministic

Five tasks explicitly named unique repository symbols.

Routing those queries through RepositoryIndex and using semantic
retrieval only for the remaining conceptual tasks preserved 8/9 Top-1
and 9/9 Top-3.

The hybrid run avoided semantic search for 5/9 queries, achieved 5/5
Top-1 on the exact-symbol route, and reduced average measured retrieval
time and retrieved context relative to the pure semantic run.

## Current retrieval architecture

Hewn should not treat repository retrieval as one universal similarity
search problem.

The current architecture is:

    query
      |
      v
    deterministic identifier resolution
      |
      +-- unique explicit symbol --> RepositoryIndex
      |
      +-- otherwise -------------> SemanticIndex
                                      |
                                      v
                               compact symbol evidence

Deterministic program knowledge is preferred when it can answer the
question directly. Semantic computation is used when structural lookup
is insufficient.

## What remains unresolved

nav-007 remains a useful failure case. Semantic retrieval ranks final
response parsing and agent orchestration above completion authorization.

This should not be corrected with benchmark-specific vocabulary.

Potential future explanations include insufficient behavioral
representation, missing relationship information, or limits of the
embedding model.

Those hypotheses should be tested only when a later module requires
them.

## What Module 4 does not establish

These experiments do not establish that:

- semantic retrieval universally outperforms BM25,
- BGE-small is the best embedding model for code,
- the hybrid router generalizes to unseen repositories,
- Hewn has achieved production-quality retrieval,
- 8/9 accuracy predicts coding-agent task success.

The benchmark contains only nine tasks against Hewn's own repository.

Generalization requires larger and unseen-repository evaluation in the
evaluation module.

## Decision

Module 4 adopts:

- RepositoryIndex for deterministic exact-symbol lookup,
- compact symbol-level retrieval documents,
- local semantic retrieval for conceptual queries,
- conservative routing between deterministic and semantic retrieval.

BM25 remains useful as a baseline and potentially as a future retrieval
signal, but the current evidence does not justify adding score fusion.

Persistent indexes, caching, context budgeting, and repository memory
are deliberately deferred to later modules.