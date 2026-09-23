# Hewn Claims and Evidence

This document records what the Hewn experiments support, what remains a hypothesis, and what the project does not claim.

Its purpose is to prevent architectural intuition, promising demos, or post-hoc interpretation from being presented as stronger evidence than the experiments provide.

## Supported Findings

### Tool interfaces can materially affect small-model navigation

In the Module 2 self-navigation benchmark:

- primitive tools: 0/9,
- scoped search: 1/9,
- semantic symbol navigation: 3/9.

This supports the narrower claim that tool design affected measured navigation performance on that task set.

It does not establish that semantic symbol tools are universally superior.

### Semantic retrieval substantially outperformed the tested lexical baselines

On the Module 4 retrieval benchmark:

- BM25: 4/9 Top-1 and 6/9 Top-3,
- semantic retrieval: 8/9 Top-1 and 9/9 Top-3,
- hybrid retrieval: 8/9 Top-1 and 9/9 Top-3.

This supports semantic retrieval as the stronger mechanism on that benchmark.

It does not establish that retrieval quality alone produces coding correctness.

### Better context improved measured downstream performance but did not solve conceptual reasoning

The production-context experiment improved final-answer success from 3/9 to 6/9.

Conceptual tasks remained 0/4 despite successful retrieval on 4/4.

This supports a separation between evidence retrieval and reasoning over evidence.

### Execution is a reliable source of mechanical feedback

Execution experiments showed that tests and checks can identify mutation outcomes mechanically.

Targeted tests are useful intermediate signals.

Full verification remains the stronger completion-grade signal.

### Deterministic checks should not be delegated to model reviewers when no new information is added

Planning and reviewer experiments did not show value from adding a model reviewer when the relevant execution state was already mechanically available.

This supports Hewn's policy of using deterministic mechanisms for mechanically decidable conditions.

### Local inference was practical on the tested workstation for the evaluated small quantized models

Measured llama.cpp experiments included:

- Qwen2.5-Coder-0.5B Q4 prompt processing around 95.15 tokens/s,
- decode around 25.96 tokens/s,
- approximately 658 MiB measured RSS,
- approximately 10.92 s measured wall time.

For the tested 1.5B Q4 model:

- prompt processing around 44.29 tokens/s,
- decode around 13.06 tokens/s,
- approximately 1951.77 MiB measured RSS,
- approximately 24.90 s measured wall time.

A 3B local experiment caused severe workstation pressure and was excluded from further local testing.

These measurements apply to the recorded hardware and configurations. They are not universal performance claims.

### Local inference feasibility did not imply local fine-tuning feasibility

A local Module 14 training attempt caused severe workstation pressure and was operationally impractical under the tested configuration.

The available evidence did not establish a specific OOM kill.

GPU training was therefore used for subsequent training experiments.

### Module 14 SFT improved protocol behavior but not held-out exact action correctness

Module 14 trained a LoRA adapter over 96 training rows.

Training loss was approximately 4.3571 after one epoch.

On 24 held-out examples:

- base exact structured-action correctness: 0/24,
- Module 14 exact structured-action correctness: 0/24.

Protocol-valid outputs increased for part of the evaluation set, but held-out action correctness remained zero.

Training loss is not treated as behavioral evidence.

### Execution-derived supervised recovery changed behavior without producing reliable executable policy

Module 15 trained on 192 rows, including execution-derived recovery examples.

Training loss was approximately 4.0417 after one epoch.

On 32 held-out recovery examples:

- base exact action correctness: 0/32,
- Module 14 exact action correctness: 0/32,
- Module 15 exact action correctness: 0/32.

Post-hoc inspection showed state-conditioned semantic changes on some recovery families.

A narrow deterministic normalizer could safely recover 16/32 outputs.

The primary exact metric remains 0/32.

### The frozen Hewn end-to-end 0.5B benchmark failed all behavioral tasks

On the frozen 12-task Module 16C benchmark:

- behavioral success: 0/12,
- hidden task-oracle success: 0/12,
- regression-oracle success: 9/12,
- tasks reaching model-selected tool use: 0/12,
- tasks reaching execution: 0/12.

This is the primary frozen end-to-end result.

### Conversation representation affected mechanical agent progression

Module 16E exposed an inconsistency where Hewn required canonical JSON model actions but wrote successful tool actions back into model-visible history using a human-readable representation.

After canonicalizing model-visible assistant action history, the paired control smoke reached a task-directed `replace_text` action.

Behavioral success remained zero.

This supports a claim about mechanical control-loop progression, not task correctness.

### More valid tool calls did not imply better behavior

In the post-fix Module 16E smoke:

- control: 1 model-selected tool call, followed by failed recovery and stagnation,
- repository-map bootstrap: 12 model-selected tool calls, all repeated `repository_map`, followed by the agent limit.

Neither solved the task.

The treatment increased valid executable interaction while producing no useful task progression.

## Architectural Decisions Supported by the Research

Hewn v0.1 therefore keeps:

- deterministic repository indexing,
- semantic retrieval,
- bounded context construction,
- strict canonical model protocol,
- narrow deterministic normalization,
- explicit normalization provenance,
- typed tools,
- authority checks,
- structured editing,
- execution feedback,
- verification-gated completion,
- telemetry,
- explicit experimental provenance.

## Hypotheses, Not Established Facts

The following remain hypotheses or future research directions:

- a stronger small local model may cross the end-to-end capability threshold,
- targeted state-conditioned policy training may outperform representation-focused SFT,
- improved recovery training may make failed-edit feedback useful,
- deterministic infrastructure may allow a smaller model to approach much larger models on selected task distributions,
- Hewn may offer favorable cost/capability tradeoffs against frontier coding agents.

These require additional experiments.

## Claims Hewn Does Not Make

Hewn v0.1 does **not** claim:

- to outperform Codex,
- to outperform Claude Code,
- to outperform frontier coding agents generally,
- that a 0.5B model is sufficient for autonomous software engineering,
- that tool count measures intelligence,
- that retrieval accuracy equals task accuracy,
- that lower training loss establishes agent improvement,
- that a model-generated final response establishes correctness,
- that the unexecuted Module 17 protocol constitutes a frontier comparison.

## Module 17

Module 17 froze a protocol and task inputs for a future frontier-agent comparison.

The comparison was not executed as part of Hewn v0.1.

No frontier-agent performance claim should therefore be derived from Module 17.

## Evidence Location

Detailed experiments, fixtures, raw results, and module-level documentation live under:

    research/

The frozen production architecture is tagged:

    hewn-v0.1-eval-freeze
