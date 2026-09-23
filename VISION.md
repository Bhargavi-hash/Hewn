# Hewn Vision

## Small models. Sharp tools.

Hewn began with a practical frustration: capable coding agents are useful, but repeated cloud inference can be expensive, opaque, and difficult to control.

The obvious response is to run a smaller model locally.

The less obvious question is whether a small model alone is enough.

Hewn's thesis is that coding-agent capability does not come only from model scale.

It emerges from the interaction between:

- the model,
- repository understanding,
- retrieval,
- context,
- tools,
- execution feedback,
- memory,
- authority,
- and the control loop.

A useful approximation is:

    agent capability
        =
    model
        x tools
        x context
        x feedback
        x control loop

This is not a literal mathematical model. It expresses the project's design philosophy: a strong model inside a weak system can waste capability, while a smaller model may become substantially more useful when deterministic mechanisms handle work that does not require generative reasoning.

## Local First

Hewn is local-first for three reasons.

### Cost

Repeated coding-agent inference should not necessarily require a recurring cloud budget.

### Control

Repository access, tool authority, execution, and completion policy should be inspectable.

### Research

Local models make it easier to separate model behavior from agent infrastructure and study where capability actually comes from.

Local-first does not mean local-only.

Training, benchmarking, or optional inference may use remote hardware when that is the practical choice.

## What Hewn Is Trying to Build

The long-term product direction is a coding agent that can:

- run primarily on developer-controlled hardware,
- understand a repository before acting,
- retrieve only relevant context,
- use structured tools,
- edit code conservatively,
- execute tests and checks,
- recover from failures,
- remember useful repository knowledge,
- expose its control boundaries,
- and remain inexpensive enough for frequent use.

The desired user experience is eventually much simpler than the v0.1 research setup:

    hewn setup
    hewn

The system should be able to detect or configure its local inference environment rather than requiring users to manually assemble every dependency.

## What Hewn Is Not Trying to Prove

Hewn v0.1 does not demonstrate that small local models universally outperform frontier models.

It does not demonstrate that deterministic infrastructure can replace model reasoning.

It does not demonstrate that the current 0.5B model is ready for autonomous software engineering.

Those would be stronger claims than the experiments support.

The project instead asks which parts of coding-agent work can be moved out of the model, which mechanisms measurably help, and where small-model capability remains the limiting factor.

## Research Philosophy

Hewn follows several rules.

### Measure components separately

A better retriever does not imply a better coding agent.

A lower training loss does not imply a better tool policy.

More tool calls do not imply more progress.

### Keep failures

Failed experiments are evidence.

They should remain reproducible rather than disappearing when a later design works better.

### Prefer mechanical answers when available

If the system can determine something reliably from repository state or execution, it should not ask a model to guess.

### Keep model authority narrow

The model proposes what it wants to do.

The system decides whether that action is valid and authorized.

### Evaluate behavior externally

The model does not grade itself.

Correctness should come from tests, hidden evaluators, repository state, and other externally observable evidence.

## The Main Open Problem

The v0.1 research increasingly points to a specific bottleneck:

> State-conditioned action policy is harder than action formatting.

A small model can learn or imitate the shape of a valid tool call while still choosing the wrong tool for the current state.

It can retrieve relevant evidence without reasoning correctly from it.

It can receive execution feedback without recovering correctly.

That is a more useful research target than merely teaching a model to emit JSON.

## Future Directions

Possible future Hewn work includes:

- stronger small local coding models,
- state-conditioned tool-policy training,
- better failed-edit recovery,
- progress-aware read-only tool-loop detection,
- execution-derived training objectives,
- improved local model setup,
- quantized deployment,
- optional remote-model adapters,
- broader repository-language support,
- controlled frontier-agent comparisons.

Future work should preserve the same experimental discipline as v0.1.

## North Star

Hewn's goal is not to make the model pretend to know everything.

It is to build a system where the model only has to be intelligent about the parts that genuinely require intelligence.
