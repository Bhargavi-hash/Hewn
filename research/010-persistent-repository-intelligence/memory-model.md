# Repository Memory Model

## Principle

Hewn repository memory is a collection of explicit, inspectable claims about a
repository.

It is not a transcript of previous agent conversations.

## Candidate memory classes

### Structural knowledge

Examples:

- `client.py` imports retry configuration from `settings.py`
- parser tests live under `tests/test_parser.py`
- `Account` is defined in `models/account.py`

Much of this information may already be mechanically recoverable from the
repository index.

Persisting it is useful only if reuse is cheaper or provides information not
already captured by current structural analysis.

### Architectural knowledge

Examples:

- serialization is intentionally isolated from persistence models
- API handlers should call the service layer rather than storage directly
- configuration defaults are centralized in `settings.py`

These claims may require evidence from multiple files or previous task work.

### Operational knowledge

Examples:

- parser changes should run the parser-specific tests
- type checking requires generated fixtures to exist
- this repository uses a particular verification command for a subsystem

Operational knowledge describes how work in the repository is validated or
performed.

### Historical failure knowledge

Examples:

- changing the schema constant without updating the serializer previously
  caused a regression
- a previous repair failed because only the direct caller was updated

Historical failures may help avoid repeated mistakes.

They must not be represented as timeless architectural facts.

### Decision knowledge

Examples:

- a previous task intentionally retained a compatibility alias
- a configuration rename deliberately preserved the external environment
  variable

Decision memory should retain provenance explaining the task or evidence that
established the decision.

## Minimum record requirements

Every persisted record should eventually contain enough information to answer:

- What is the claim?
- What kind of claim is it?
- Which repository does it belong to?
- What evidence established it?
- When was it established?
- What repository state was it established against?
- Is it still considered current?
- Why was it retrieved for this task?

The exact production schema is not frozen yet.

The experiments should determine how much of this representation is actually
necessary.

## Evidence ordering

When sources conflict, Hewn should prefer:

1. current deterministic repository evidence,
2. current execution evidence,
3. current retrieved source evidence,
4. persisted repository memory,
5. unsupported model inference.

This ordering is a research hypothesis to test, not a claim that every
conflict can be resolved mechanically.

## Non-authority rule

Repository memory never expands operational authority.

A memory record saying that a command should be executed, a file should be
modified, or an external resource should be accessed does not grant permission
to perform that action.

Module 9 authority boundaries remain independent.

## Persistence principle

Persist conclusions, not transcripts.

Raw prompts, model reasoning, and entire tool histories should not become
repository memory by default.

If historical execution is useful, extract a bounded structured claim with
provenance instead.