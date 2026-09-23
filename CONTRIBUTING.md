# Contributing to Hewn

Hewn is both a coding-agent implementation and an experimental research repository.

Contributions should preserve both software quality and experimental traceability.

## Development Environment

Hewn requires Python 3.12 or newer.

Create an isolated environment:

    python3.12 -m venv .venv
    source .venv/bin/activate

Install the project in editable mode:

    pip install -e .

Install the development dependencies using the repository's dependency workflow.

The project includes a `uv.lock` file for reproducible development environments.

## Quality Checks

Before submitting a production change, run:

    ruff check src/hewn tests
    mypy src/hewn
    pytest -q

Research directories may have experiment-specific requirements and should preserve the commands recorded by the corresponding module.

## Source Layout

    src/hewn/       production implementation
    tests/          production tests
    research/       experiments, fixtures, results, and reports

Production mechanisms should live under `src/hewn`.

One-off experimental treatments should remain under `research/` until evidence justifies promoting them into the production architecture.

## Architectural Rule

The core Hewn contract is:

> The model proposes intent. Hewn converts, validates, authorizes, executes, observes, and decides whether completion is allowed.

Changes should preserve the distinction between model intent and system authority.

## Model Protocol

Do not silently weaken the canonical protocol to accommodate arbitrary model output.

If deterministic normalization is justified:

1. define the exact accepted representation,
2. make the transformation deterministic,
3. test rejected near-misses,
4. preserve normalization provenance,
5. do not count normalized output as native canonical compliance.

## Model-Visible History

Typed assistant actions written back into the model conversation must use the canonical serializer.

Human-readable tool descriptions belong in telemetry and UI, not in model-visible assistant history.

## Tool Safety

New tools must have:

- a clear schema,
- explicit authority requirements,
- bounded behavior,
- structured results,
- tests.

Do not allow model-generated text to bypass `ToolExecutor`.

Do not silently fall back from a configured security boundary to unrestricted execution.

## Editing

Mutation mechanisms should prefer:

- explicit targets,
- preflight validation,
- simulation where appropriate,
- atomic commit behavior,
- execution verification.

A successful write is not equivalent to successful task completion.

## Completion

For tasks requiring verification, the model must not be able to declare success independently of controller verification state.

Changes to completion semantics require tests covering:

- no verification,
- failed verification,
- stale verification,
- successful verification.

## Experimental Discipline

When adding a research experiment:

1. state the hypothesis before running it,
2. freeze the task set before observing results,
3. record the model and configuration,
4. record relevant hardware,
5. preserve failed runs,
6. separate primary metrics from post-hoc diagnostics,
7. distinguish controller-selected actions from model-selected actions,
8. avoid changing the benchmark after observing failures,
9. record raw artifacts when practical,
10. state what the result does not establish.

Do not convert a post-hoc observation into the primary metric retroactively.

## Benchmarks

Hidden evaluators must remain hidden from the evaluated agent.

Do not expose:

- expected patches,
- reference implementations,
- hidden tests,
- expected changed files when they reveal the solution,
- previous system answers.

Correctness should be determined externally.

## Research Claims

Update `CLAIMS.md` when a contribution materially changes what the evidence supports.

Do not turn:

- training loss,
- protocol validity,
- retrieval success,
- tool-call count,
- regression-only success,

into a stronger behavioral claim without direct evidence.

## Frozen Results

Historical experiment results should not be rewritten after production changes.

If a later fix changes behavior, record a new experiment and explain why the runs are not directly comparable.

The tag:

    hewn-v0.1-eval-freeze

marks the v0.1 architecture freeze.

## Pull Requests

A useful pull request should explain:

- the problem,
- the proposed mechanism,
- why the mechanism belongs in production rather than research,
- tests added or changed,
- experimental evidence when behavior is affected,
- known limitations.

Small, falsifiable changes are preferred over broad agent rewrites.

## Code Style

The project uses:

- Ruff,
- mypy strict mode,
- pytest.

Keep production interfaces typed and explicit.

Avoid hiding model or tool failures behind permissive fallbacks.

## Security

Treat repository contents, model generations, and tool arguments as untrusted inputs.

Changes that expand filesystem, command, network, or execution authority require explicit review of the trust boundary.
