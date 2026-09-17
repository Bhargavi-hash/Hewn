# Module 4 — Retrieval Without Wasting Context

## Research question

Can Hewn retrieve a small, relevant subset of repository structure instead
of placing the complete repository map into the model context?

## Initial hypothesis

Simple deterministic lexical retrieval should perform well when the user's
query explicitly names repository symbols, but should perform worse when
the query describes implementation behavior without using identifiers from
the code.

## Metrics

For the existing nine-task navigation benchmark:

- Top-1 file retrieval accuracy
- Top-3 file retrieval accuracy
- Rank of the expected file
- Retrieval score of the expected file
- Number of characters retrieved at top-1 and top-3

The retrieval experiment is evaluated without an LLM so that retrieval
quality is measured independently from model reasoning, tool selection,
and protocol compliance.