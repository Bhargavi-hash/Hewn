# Hewn

**Small models. Sharp tools.**

Hewn is a local-first coding agent built around a simple question:

> How much coding-agent capability can come from the system around the model rather than from making the model larger?

Instead of asking an LLM to understand a repository, choose context, edit files, execute commands, recover from failures, and decide when a task is complete entirely on its own, Hewn separates those responsibilities.

The model proposes intent. Hewn handles repository understanding, retrieval, context construction, protocol validation, authority, tool execution, execution feedback, and completion policy.

Hewn v0.1 is both a working experimental coding-agent stack and the result of a 16-module investigation into coding-agent architecture.

## Why Hewn?

Modern coding agents are often discussed primarily in terms of model capability. Hewn explores a different design space:

- Can deterministic repository analysis reduce work the model has to do?
- How much does retrieval quality affect a small coding model?
- Which decisions should belong to an LLM, and which should be mechanical?
- Can execution act as feedback rather than merely a final test?
- Can a small model learn tool use and recovery policies?
- Where does a small local model actually fail once the surrounding agent is reasonably strong?

The project is local-first, not local-dogmatic. Local inference is a deployment goal. Training and controlled experiments may use other hardware when necessary.

## Current Status

Hewn v0.1 is a research-grade local coding agent.

It is **not** a claim that a 0.5B local model matches frontier coding agents.

The frozen 12-task end-to-end evaluation with Qwen2.5-Coder-0.5B-Instruct achieved:

| Metric | Result |
| --- | ---: |
| Behavioral success | 0/12 |
| Hidden task-oracle success | 0/12 |
| Regression-oracle success | 9/12 |
| Tasks reaching model-selected tool use | 0/12 |
| Tasks reaching execution | 0/12 |

Later integration work found a model-conversation representation inconsistency. After fixing it, a controlled smoke test progressed to a task-directed edit, but behavioral correctness remained zero.

A deterministic repository-map bootstrap then caused the model to make 12 consecutive valid `repository_map` calls without progressing to reading, editing, or verification.

That distinction is important to Hewn:

> Valid tool use is not the same thing as useful agent behavior.

See [CLAIMS.md](CLAIMS.md) for the evidence boundaries behind project claims.

## Architecture

At a high level:

    User task
        |
        v
    Repository index + retrieval
        |
        v
    Bounded context
        |
        v
    Local coding model
        |
        v
    Canonical action protocol
        |
        v
    Narrow deterministic normalization
        |
        v
    Authority + validation
        |
        v
    Tools
        |
        v
    Execution observation
        |
        v
    Controller state
        |
        v
    Verification gate
        |
        v
    Final response

The core contract is:

> **The model proposes intent. Hewn converts, validates, authorizes, executes, observes, and decides whether completion is allowed.**

See [ARCHITECTURE.md](ARCHITECTURE.md) for the detailed design.

## What Hewn Includes

Hewn v0.1 includes:

- repository indexing and symbol extraction,
- lexical, BM25, semantic, and hybrid retrieval experiments,
- bounded context construction,
- a strict structured model protocol,
- narrow deterministic action normalization,
- repository read and search tools,
- structured and atomic editing,
- sandboxed execution through Bubblewrap,
- normalized execution feedback,
- verification-gated completion,
- stagnation detection,
- repository memory experiments,
- telemetry,
- benchmark infrastructure,
- llama.cpp integration,
- LoRA/SFT and execution-derived recovery experiments.

## Requirements

The Python package requires:

- Python 3.12 or newer.

The default CLI additionally expects:

- a local llama.cpp-compatible inference server,
- the model expected by your local llama.cpp configuration,
- Bubblewrap (`bwrap`) for execution,
- the semantic embedding dependency used by Hewn.

The default semantic retriever uses:

    BAAI/bge-small-en-v1.5

The current CLI assumes the local model server is available through Hewn's `LlamaCppModel` configuration.

Hewn v0.1 does not yet provide a one-command model downloader or inference-server manager.

## Development Installation

Clone the repository and create a Python 3.12 environment:

    git clone <YOUR-HEWN-REPOSITORY-URL>
    cd Hewn

    python3.12 -m venv .venv
    source .venv/bin/activate

Install the package and development dependencies using the environment workflow used by the repository.

For an editable package install:

    pip install -e .

The installed command is:

    hewn --help

Expected interface:

    usage: hewn [-h] [--workspace WORKSPACE] [--trace] [--verify] request

## Running Hewn

Once the local inference backend and dependencies are configured:

    hewn "Explain the repository structure"

Run against another repository:

    hewn --workspace /path/to/repository "Find where authentication is implemented"

Show the execution trace:

    hewn --trace "Investigate the failing test"

Require successful verification before Hewn is allowed to finish:

    hewn --verify "Fix the slug normalization bug"

`--verify` is important for mutation tasks because it changes completion from an unconstrained final response to a verification-gated one.

## Research Results

Several intermediate experiments improved individual mechanisms substantially without producing end-to-end task-solving capability.

Examples:

| Experiment | Result |
| --- | --- |
| Self-navigation tools | Primitive 0/9; scoped search 1/9; semantic symbol tool 3/9 |
| BM25 retrieval | Top-1 4/9; Top-3 6/9 |
| Semantic retrieval | Top-1 8/9; Top-3 9/9 |
| Production context experiment | Final-answer success 3/9 to 6/9 |
| Module 14 held-out SFT | 0/24 exact structured actions |
| Module 15 held-out recovery | 0/32 exact structured actions |
| Module 15 post-hoc safe normalization | 16/32 recoverable |
| Frozen end-to-end benchmark | 0/12 behavioral success |
| Repository bootstrap smoke | 12 valid repeated tool calls, 0 useful progression |

One of the central findings is that improvements in components do not automatically compose into agent intelligence.

Retrieval can find the right evidence while the model still fails to reason over it. Training can improve action shape without producing the correct action policy. A controller can induce valid tool use while making the trajectory less useful.

## Research Modules

The project was developed through the following sequence:

1. Agent Loop
2. Tools Are Part of Intelligence
3. Understanding a Repository
4. Retrieval Without Wasting Context
5. Context Engineering
6. How Coding Agents Edit Code
7. Execution as Feedback
8. Planning and Subagents
9. Agent Security
10. Persistent Repository Intelligence
11. Evaluating Coding Agents Properly
12. Running Models Locally
13. Why Small Models Fail
14. Training a Tool-Using Coding Model
15. Execution-Based Training
16. Building Hewn
17. Frontier comparison protocol

Module 17 prepares a frozen frontier-agent comparison protocol but does not claim comparison results that were not executed.

Research artifacts live under `research/`.

## Design Principles

### Models propose; the system authorizes

Model output is not authority. Tool calls pass through schema validation and explicit authorization before execution.

### Deterministic mechanisms should remain deterministic

Hewn does not ask a second model to decide something the controller can establish mechanically.

### Execution is evidence

Tests and commands provide state information to the agent loop. They are not merely a final score.

### Completion is a policy decision

For verified tasks, saying "done" is insufficient. Hewn can require successful verification before accepting completion.

### Representation repair is narrow

The action normalizer repairs only explicitly supported representation differences. It does not silently infer arbitrary tools or arguments.

### Failed experiments stay visible

Negative results are part of the project. Hewn does not rewrite its experimental history around successful demonstrations.

## Current Limitations

Hewn v0.1 has significant limitations:

- the evaluated 0.5B model is not a reliable autonomous coding agent,
- state-conditioned tool selection remains weak,
- recovery after failed edits remains weak,
- successful retrieval does not guarantee correct reasoning,
- local model and llama.cpp setup is still manual,
- semantic retrieval adds an additional model dependency,
- the CLI is research-oriented rather than consumer-oriented,
- frontier-agent comparison results have not yet been executed.

These are research boundaries, not hidden product limitations.

## Repository Guide

- `src/hewn/` — production Hewn implementation
- `tests/` — production tests
- `research/` — module experiments, fixtures, evaluations, and results
- `ARCHITECTURE.md` — production architecture
- `VISION.md` — project motivation and direction
- `CLAIMS.md` — evidence and claim boundaries
- `CONTRIBUTING.md` — development and experimental rules

## Version

The evaluation-frozen architecture is tagged:

    hewn-v0.1-eval-freeze

This tag marks the Hewn architecture before any future frontier comparison results are observed.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

Apache-2.0 license