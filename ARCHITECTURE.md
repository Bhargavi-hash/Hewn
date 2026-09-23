# Hewn Architecture

## Overview

Hewn is a local-first coding-agent architecture designed around a separation of responsibilities between probabilistic model behavior and deterministic system mechanisms.

The central contract is:

> **The model proposes intent. Hewn converts, validates, authorizes, executes, observes, and decides whether completion is allowed.**

The model is therefore one component of the agent rather than the entire agent.

## Production Flow

    User request
        |
        v
    Repository understanding
        |
        +-- repository index
        +-- symbols and imports
        +-- retrieval
        |
        v
    Context construction
        |
        v
    Local model
        |
        v
    Model protocol boundary
        |
        +-- strict canonical parser
        +-- narrow deterministic normalization
        +-- provenance
        |
        v
    Typed action
        |
        v
    Authority and schema validation
        |
        v
    Tool execution
        |
        +-- repository reads
        +-- search
        +-- structured edits
        +-- execution/checks
        |
        v
    Normalized observation
        |
        v
    Controller state
        |
        +-- repository mutation state
        +-- verification state
        +-- stagnation state
        |
        v
    Completion policy
        |
        v
    Final response

## Agent Loop

`src/hewn/agent.py` owns the primary control loop.

The model receives conversation state and available tool definitions and returns one of two typed intents:

- a tool call,
- a final response.

A tool call is not executed directly by the model.

It moves through Hewn's trusted execution path before becoming an observation visible to the next model turn.

The reusable `run_messages` boundary allows the controller to run the same loop over an explicitly constructed conversation while preserving the production execution semantics.

## Canonical Model Protocol

Hewn uses a strict model-visible protocol.

Canonical tool call:

    {
      "type": "tool_call",
      "name": "read_file",
      "arguments": {
        "path": "src/example.py"
      }
    }

Canonical final response:

    {
      "type": "final",
      "text": "..."
    }

Unknown keys and unsupported shapes are rejected by the strict parser.

A narrow normalizer may recover explicitly supported representation aliases, but normalized responses retain separate provenance.

Native protocol compliance and deterministic repair are not treated as the same metric.

## Conversation Representation

A production invariant discovered during Module 16 is:

> Every typed assistant action written back into model-visible conversation history must use the canonical model protocol.

Human-readable descriptions belong in telemetry or UI, not in the model conversation.

This matters because a small model can imitate the representation of previous assistant actions even when that representation conflicts with the protocol it is expected to emit.

## Repository Understanding

Hewn constructs a deterministic repository index rather than requiring the model to discover the repository entirely through blind navigation.

The repository layer captures information such as:

- files,
- symbols,
- imports,
- structural relationships.

This information feeds retrieval and context construction.

The repository index is evidence for the model, not model-generated memory.

## Retrieval

The project experimentally compared several retrieval strategies, including:

- lexical retrieval,
- BM25,
- semantic retrieval,
- hybrid routing,
- symbol-oriented retrieval.

Semantic retrieval materially outperformed simple lexical retrieval on the research benchmark, but retrieval success did not guarantee task-solving success.

This distinction is fundamental:

> Finding the right evidence and reasoning correctly from that evidence are separate capabilities.

## Context Construction

Retrieved evidence is converted into a bounded context rather than indiscriminately placing repository contents into the prompt.

The context layer controls what repository evidence reaches the model and keeps context consumption explicit.

Hewn distinguishes configured model context capacity from context actually consumed by the task.

## Tool Boundary

Tool calls use typed `ToolCall` objects.

The tool executor performs:

1. tool lookup,
2. argument schema validation,
3. authority checks,
4. handler execution,
5. structured result production.

The model cannot bypass this boundary merely by emitting text that resembles a command.

## Authority

Authority is separate from model intent.

The production CLI currently grants repository reads, repository writes, and approved checks through an explicit `AuthorityGrant`.

The authority layer exists so that a future policy can restrict capabilities without changing model behavior.

The principle is:

> Model intent is not execution authority.

## Editing

Hewn's editing work converged on a structured mutation pipeline:

    candidate edit
        |
        v
    preflight
        |
        v
    simulation
        |
        v
    atomic commit
        |
        v
    execution verification

Structured editing reduces ambiguity relative to unrestricted text generation over whole files.

Mutation itself is not considered successful task completion.

## Execution

Execution provides feedback to the controller and model.

Hewn normalizes execution outcomes so the agent can distinguish useful states such as:

- successful checks,
- failed checks,
- rejected edits,
- missing targets,
- stale verification.

Execution is therefore both an evaluator and an information source.

## Completion Policy

Hewn separates model final responses from controller completion decisions.

Two important completion modes are:

- `NONE`,
- `VERIFIED`.

Under `VERIFIED`, a final model response is insufficient unless the controller has observed successful verification.

Repository mutation can make previous verification stale.

A failed check blocks verified completion.

This prevents the model from unilaterally declaring a mutation task complete.

## Stagnation

The agent tracks non-progressing turns and can terminate a run when repeated responses fail to change useful state.

Module 16 also exposed a remaining limitation: repeated successful read-only calls can still be mechanically valid while making no semantic progress.

This is a potential direction for future controller work.

## Local Model Boundary

The production CLI uses `LlamaCppModel`.

The model boundary is intentionally replaceable. Hewn's architecture should not depend on a particular parameter count or model family.

The v0.1 research evaluation used Qwen2.5-Coder-0.5B-Instruct as the primary small-model baseline.

## Semantic Embeddings

The default CLI semantic embedding model is:

    BAAI/bge-small-en-v1.5

Semantic embeddings support retrieval; they are not used as a substitute for the coding model.

## Sandboxed Execution

The production CLI constructs a `BubblewrapExecutionBackend`.

Execution is therefore intended to occur through an explicit isolation boundary rather than unrestricted shell access.

Hewn does not silently fall back from a requested security boundary to unrestricted execution.

## Telemetry

Agent telemetry records information such as:

- model calls,
- tool calls,
- successful and failed tool calls,
- wall time,
- protocol events,
- model responses,
- tool results,
- completion rejections,
- stagnation.

Telemetry is used for research and debugging but does not itself grant authority.

## Persistent Repository Intelligence

Hewn explored persistent repository memory under the principle:

> Remember what the repository cannot cheaply reconstruct; recompute what it can.

Stored information is evidence, not authority.

Repository-derived state can become stale and must not silently override current source state.

## Trusted and Untrusted Boundaries

### Untrusted or probabilistic

- model generations,
- inferred task strategy,
- proposed actions.

### Deterministic or trusted mechanisms

- repository parsing,
- schema validation,
- action authorization,
- file boundaries,
- edit application,
- execution results,
- verification state,
- completion policy.

This separation is one of Hewn's main architectural commitments.

## Frozen v0.1 Boundary

The production architecture used for the final research freeze is tagged:

    hewn-v0.1-eval-freeze

Experimental Module 16 repository bootstrapping is not part of the default production path.

The architecture should not be retroactively changed and then attributed to results collected against the frozen version.
