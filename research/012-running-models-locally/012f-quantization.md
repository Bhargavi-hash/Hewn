# 012F — Quantization Tradeoffs

## Research question

How does quantization affect artifact size, process memory, inference
performance, and coding-relevant model behavior when model family,
runtime, hardware, and inference configuration are held fixed?

## Motivation

Quantization is often described primarily as a way to make models
smaller or faster.

For a local coding agent, that description is incomplete.

A quantization choice can affect several distinct properties:

- model artifact size;
- process memory requirements;
- prompt-processing throughput;
- autoregressive decode throughput;
- end-to-end latency;
- model output quality.

These properties must be measured separately.

A smaller artifact does not necessarily imply proportionally lower
runtime memory, faster inference, or unchanged coding capability.

## Hypothesis

More aggressive quantization will reduce model artifact size and may
reduce runtime memory requirements, but its effects on inference
throughput and model behavior will not necessarily move in the same
direction or by the same magnitude.

Quantization should therefore be treated as a systems tradeoff rather
than as a single compression ratio.

## Independent variable

Quantization level.

Use quantizations from the same model family and GGUF repository:

`Qwen/Qwen2.5-Coder-1.5B-Instruct-GGUF`

Candidate conditions:

- Q8_0
- Q6_K
- Q5_K_M
- Q4_K_M
- Q3_K_M

The exact final set must be frozen before measured inference begins.

If a candidate cannot run reliably on the experimental machine, record
that as an operational result rather than silently replacing it.

## Controlled variables

Hold fixed:

- model family and parameter count;
- llama.cpp runtime commit;
- hardware;
- CPU thread count;
- configured context capacity;
- consumed prompt;
- prompt-cache state;
- temperature;
- maximum generation length;
- parallel slots;
- request protocol;
- repetition count.

Baseline inference configuration:

- threads: 4
- configured context: 8192
- parallel slots: 1
- prompt cache: disabled
- temperature: 0
- maximum generation: 128 tokens

## Workload

Use a frozen prompt from the existing Module 12 context experiments.

Primary performance workload:

- 1024 actual prompt tokens

Rationale:

1024 tokens is large enough to exercise meaningful uncached prefill
work while remaining inexpensive enough to repeat across several
quantizations on the experimental CPU.

Do not modify the prompt after observing quantization results.

## Repetitions

Run five measured repetitions per quantization.

Use a fresh llama-server process for every quantization condition.

All five repetitions for one quantization may execute within that
process.

Prompt caching must remain disabled.

## Measurements

### Artifact

Record:

- exact model identifier;
- exact quantization;
- local artifact size in bytes;
- artifact size in MiB.

### Memory

Record process memory using the existing explicit server-PID
instrumentation.

For each condition preserve:

- memory immediately before each request;
- memory immediately after each request;
- VmRSS;
- VmHWM;
- VmSize;
- VmPeak;
- anonymous RSS;
- file-backed RSS;
- swap.

VmHWM is process-lifetime state and must not be interpreted as
per-request allocation.

### Prefill

Record:

- prompt tokens;
- cached prompt tokens;
- evaluated prompt tokens;
- prompt seconds;
- prompt tokens per second.

### Decode

Record:

- generated tokens;
- generation seconds;
- generation tokens per second;
- finish reason.

### End-to-end

Record:

- wall-clock request time.

### Accounting

Require:

- prompt tokens equal the frozen workload;
- cached prompt tokens equal zero;
- evaluated prompt tokens equal prompt tokens;
- total token accounting passes;
- prompt-cache accounting passes;
- generation accounting passes.

## Behavioral evaluation

Performance and behavioral quality are separate measurements.

Do not infer coding capability from tokens per second.

After the systems measurements are complete, evaluate whether the
quantizations produce different behavior on a small frozen
coding-relevant workload.

The behavioral workload and evaluator must be frozen before observing
its outputs.

Do not select tasks after seeing which quantization performs poorly.

## Analysis

For each quantization report:

- artifact size;
- fresh-server idle RSS;
- observed process-lifetime HWM;
- median prefill seconds;
- median prefill tokens/second;
- median decode tokens/second;
- median wall time;
- generated-token counts and finish reasons.

Preserve individual repetitions in addition to aggregates.

Do not construct a weighted combined score.

## Decision rules

A quantization may be described as smaller only from measured artifact
size.

A quantization may be described as using less observed process memory
only from measured process-memory data.

A quantization may be described as faster only for the particular
measured inference dimension that supports the statement.

A quantization may be described as preserving or degrading behavioral
capability only from the frozen behavioral evaluation.

Do not infer one property from another.

## Threats to validity

This experiment is scoped to:

- one model family;
- one parameter count;
- one llama.cpp build;
- one CPU;
- one primary inference workload;
- a small number of repetitions.

Results must not be presented as universal properties of GGUF
quantization.

Differences between quantizations may interact with llama.cpp kernels,
hardware characteristics, workload length, and model architecture.

## Design principle

> Quantization changes representation. Measure its effects on memory,
> speed, and behavior separately.