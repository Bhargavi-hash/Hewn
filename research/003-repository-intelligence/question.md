# Module 3 — Understanding a Repository

## Research Question

Can deterministic program analysis provide enough structural repository
knowledge to reduce the amount of repository inference required from a small
coding model?

## Motivation

Module 2 showed that semantic symbol lookup can improve exact-symbol
navigation, but conceptual navigation remained difficult.

`find_symbol` works when the relevant symbol name is already known.

A coding agent must also answer questions where the user describes behavior
rather than implementation names.

Examples:

- Where is workspace escape prevention implemented?
- What decides whether the agent can finish?
- What converts a model action into tool execution?

These tasks require repository understanding before exact lookup is possible.

## Primary Hypothesis

A deterministic repository index containing files, symbols, imports, and
structural relationships can provide useful grounding before model reasoning,
reducing unsupported architectural guesses.

## Initial Scope

The first implementation will support Python repositories using the standard
library AST.

The repository model itself should not be Python-specific.

## Initial Structural Knowledge

The index should represent:

- source files
- classes
- functions
- methods
- symbol locations
- imports
- containment relationships

Later experiments may justify additional relationships.

## Constraints

- Do not add relationships merely because they may be useful.
- Keep parsing separate from repository representation.
- Keep repository representation separate from model prompting.
- Preserve deterministic behavior.
- Do not introduce embeddings yet.
- Do not introduce persistent repository memory yet.
- Do not introduce tree-sitter until the language-independent abstraction is
  established.

## Relationship to Later Modules

Module 3 builds structural repository knowledge.

Module 4 will study retrieval over that knowledge.

Module 5 will decide how retrieved knowledge enters model context.

Module 10 will address persistence and incremental repository intelligence.