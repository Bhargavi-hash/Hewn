# Module 12 — Running Models Locally

## Central research question

How do model size, quantization, context length, and inference
configuration affect the latency, memory use, and coding-agent capability
of local models on fixed hardware?

## Motivation

Hewn is intended to make small local models perform far above their
weight.

Before changing models, training models, or diagnosing why small models
fail, Hewn needs a reproducible understanding of the local inference
system itself.

A model run is affected by more than model identity.

Observed behavior can depend on:

- parameter count;
- numerical precision and quantization;
- context length;
- actual prompt length;
- KV-cache size;
- prompt processing;
- autoregressive decoding;
- CPU threading;
- memory bandwidth;
- GPU offloading when available;
- batching;
- sampling configuration;
- inference-server configuration.

Without controlling these variables, comparisons between local models
can confound model capability with inference configuration.

Module 12 therefore establishes the local inference measurement layer
that Modules 13–15 will rely on.

## Primary hypothesis

Local coding-model configurations occupy measurable tradeoffs between:

```text
behavioral capability
memory consumption
prompt-processing latency
generation latency
context capacity
```

and those dimensions should be measured separately rather than reduced
to a single local-model score.

## Secondary hypotheses

### H1 — Prefill and decode are different workloads

Processing the input context and generating output tokens have different
performance characteristics and should be measured separately where the
runtime exposes sufficient information.

### H2 — Configured context is not consumed context

A server configured for a large maximum context may reserve or allocate
resources differently even when a request uses only a small portion of
that context.

Benchmark records should therefore distinguish configured context length
from actual request context.

### H3 — Quantization is a systems tradeoff

Lower-precision model representations may reduce model memory and change
inference speed, but behavioral effects must be measured rather than
assumed.

File size alone is not sufficient evidence of runtime memory use or
coding-agent capability.

### H4 — Tokens per second is not agent capability

A configuration with higher generation throughput may still perform
worse as a coding agent.

Inference throughput and Hewn behavioral success must therefore remain
separate measurements.

### H5 — Model calls are not equal-cost units

Module 11 records model-call counts as an efficiency dimension.

Module 12 should refine this by measuring inference-level work where
available, because two model calls can differ substantially in prompt
length, generated tokens, model size, and latency.

### H6 — Local inference needs provenance

Meaningful comparisons require recording enough information to reproduce
the inference environment, including model identity, quantization,
runtime configuration, hardware, and relevant request parameters.

## Fixed initial environment

The initial experiments use the existing Hewn development machine:

```text
CPU: Intel Core i5-10210U
CPU cores: 4 physical / 8 logical
RAM: approximately 7.6 GiB
GPU: no NVIDIA GPU available
Operating environment: Linux
Inference runtime: llama.cpp
```

The initial known-working model is:

```text
Qwen/Qwen2.5-Coder-1.5B-Instruct-GGUF
quantization: Q4_K_M
```

The existing known-working llama.cpp configuration is:

```text
threads: 4
context length: 4096
host: 127.0.0.1
port: 8080
```

These values describe the initial baseline.

Experiments may deliberately vary a field only after the relevant
experiment freezes that variable.

## Measurement layers

Module 12 separates three layers.

### Layer 1 — Model artifact

Examples:

```text
model family
parameter scale
quantization
GGUF artifact
artifact size
```

### Layer 2 — Inference runtime

Examples:

```text
llama.cpp version
thread count
configured context
batch configuration
CPU/GPU placement
sampling parameters
```

### Layer 3 — Request/run

Examples:

```text
actual prompt size
generated output size
prompt-processing time
generation time
wall time
memory observations
```

Agent-level behavioral correctness remains a separate evaluation layer
provided by Hewn Bench.

## Proposed experiments

### 012A — Inference anatomy and observability

Determine what the current llama.cpp runtime exposes reliably.

Identify measurable fields for:

- model metadata;
- quantization;
- configured context;
- prompt token count;
- generated token count;
- prompt-processing latency;
- generation latency;
- throughput;
- wall time;
- memory use.

The output of 012A is primarily a measurement contract.

### 012B — Reproducible inference harness

Implement the smallest reusable measurement harness needed to record
local inference runs.

The harness should preserve raw measurements and provenance.

Do not add optimization logic.

### 012C — Context scaling

Hold model and major runtime settings fixed while varying configured
context length and/or controlled prompt length.

Measure the resulting latency and memory behavior.

Configured context and actual consumed context must remain distinct.

### 012D — Thread scaling

On the fixed CPU machine, vary llama.cpp thread count under controlled
requests.

Measure prompt processing and generation separately where possible.

Do not assume the maximum logical-thread count is optimal.

### 012E — Quantization comparison

If compatible artifacts are available for the same model family and
parameter scale, compare selected quantizations under the same benchmark
conditions.

Measure:

- artifact size;
- memory;
- latency;
- throughput;
- behavioral outcomes.

Do not rank quantizations using file size or throughput alone.

### 012F — Model-size comparison

Compare a small number of local coding-model scales that can be run
reasonably on the available machine.

Keep the benchmark and inference configuration as comparable as
practical.

This experiment establishes a local capability/compute frontier rather
than searching for a universal best model.

### 012G — Agent-level synthesis

Run selected local inference configurations through Hewn Bench.

Compare inference-level measurements with:

```text
protocol validity
task correctness
regression correctness
behavioral success
agent resource usage
```

This determines which inference configurations are worth carrying into
Module 13.

## Experimental discipline

For every controlled comparison:

1. freeze the model and runtime configuration before observing results;
2. vary only the intended experimental variable where practical;
3. preserve failed runs;
4. record raw measurements;
5. record hardware and runtime provenance;
6. distinguish configured values from observed values;
7. distinguish inference throughput from behavioral capability;
8. avoid changing benchmark tasks in response to model performance;
9. use repeated runs where runtime variability matters;
10. preserve negative results.

## Metrics

Potential inference metrics include:

```text
prompt_tokens
completion_tokens
prompt_seconds
completion_seconds
prompt_tokens_per_second
completion_tokens_per_second
wall_time_seconds
peak_memory
model_artifact_bytes
configured_context
```

A metric is not promoted into the production measurement contract merely
because it is desirable.

012A must first establish that it can be measured reliably with the
current runtime.

## Relationship to Hewn Bench

Module 11 established:

```text
correctness first
efficiency second
```

Module 12 preserves that rule.

Inference metrics explain the computational cost of an agent outcome.

They do not redefine behavioral success.

A faster failed run remains a failed run.

A slower successful run remains successful while carrying a higher
observed inference cost.

## Non-goals

Module 12 does not attempt to:

- train a model;
- fine-tune a model;
- explain every small-model reasoning failure;
- redesign the Hewn agent loop;
- optimize prompts for individual benchmark tasks;
- compare Hewn with Codex or Claude Code;
- establish a universal best quantization;
- establish a universal best local model;
- build a public leaderboard.

Those belong to later modules.

## Desired outcome

At the end of Module 12, Hewn should have:

1. a reproducible local-inference measurement contract;
2. an understanding of prefill versus decode behavior;
3. measured context and threading effects on the current machine;
4. measured quantization/model-size tradeoffs where hardware permits;
5. selected local configurations for Module 13;
6. inference provenance that can be attached to later Hewn Bench runs.

The module should make statements such as:

> On this hardware, under this llama.cpp configuration, configuration X
> used these resources and produced these observed inference and
> behavioral measurements.

It should not make unsupported statements such as:

> X is the best local coding model.

## Design principle

> Measure the inference system before optimizing the model.