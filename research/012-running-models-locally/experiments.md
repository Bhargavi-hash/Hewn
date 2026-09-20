# Module 12 Experiments — Running Models Locally

## 012A — Inference anatomy and observability

### Research question

What inference-level measurements does the current llama.cpp runtime
expose reliably enough to form the initial Hewn local-inference
measurement contract?

### Purpose

Before building an inference benchmark harness, inspect the actual
runtime interface.

The goal is to avoid:

- estimating tokens when the runtime exposes token counts;
- treating total HTTP latency as generation latency;
- conflating prompt processing with autoregressive decoding;
- losing cache information;
- recording model configuration without runtime provenance.

012A is an observability experiment.

It does not compare models or optimize inference.

### Frozen runtime

The observed llama.cpp checkout is:

```text
commit:
930e2fa5995789efbf249a8bf61325bb626e417b

git describe:
v0.4.1-27-g930e2fa59

llama-server version:
0.4.1-dev

build:
10991

short commit:
930e2fa59

compiler:
GNU 11.4.0

platform:
Linux x86_64
```

The response reported:

```text
system_fingerprint:
b10991-930e2fa59
```

### Frozen model configuration

Model:

```text
Qwen/Qwen2.5-Coder-1.5B-Instruct-GGUF:Q4_K_M
```

Runtime configuration:

```text
threads = 4
configured context = 4096
host = 127.0.0.1
port = 8080
temperature = 0
max_tokens = 64
```

### Frozen request

The user message was:

```text
Write a Python function add(a, b) that returns the sum of a and b.
```

### Observed response

The model returned a Python implementation of `add`.

The response completed with:

```text
finish_reason = stop
```

### Observed usage fields

The OpenAI-compatible response exposed:

```text
prompt_tokens = 47
completion_tokens = 17
total_tokens = 64
cached_tokens = 5
```

The accounting relation for this request was:

```text
47 + 17 = 64
```

### Observed timing fields

The response also exposed:

```text
cache_n = 5

prompt_n = 42
prompt_ms = 714.381
prompt_per_token_ms = 17.009071428571428
prompt_per_second = 58.79215712623937

predicted_n = 17
predicted_ms = 1201.587
predicted_per_token_ms = 75.0991875
predicted_per_second = 13.315723289283257
```

### Prompt-token interpretation

The observed fields satisfy:

```text
cache_n + prompt_n = prompt_tokens
5 + 42 = 47
```

For this request, `prompt_n` therefore represents prompt tokens evaluated
by the runtime rather than the complete logical prompt-token count.

`usage.prompt_tokens` should be preserved as the total prompt-token
measurement.

`timings.prompt_n` and `timings.cache_n` should also be preserved
separately because they describe inference work performed by the
runtime.

012A does not yet assume that this relation will hold for every future
llama.cpp version or caching mode.

The measurement harness should validate rather than silently assume the
relationship when both fields are available.

### Completion-token interpretation

The observed fields satisfy:

```text
predicted_n = completion_tokens
17 = 17
```

For this request, llama.cpp's predicted-token count agrees with the
OpenAI-compatible completion-token count.

Both raw fields should remain available where practical.

### Prefill versus decode

The runtime exposes prompt processing and generation separately.

For this request:

```text
prompt processing:
42 evaluated tokens
714.381 ms
58.792 tokens/s

generation:
17 predicted tokens
1201.587 ms
13.316 tokens/s
```

Therefore Hewn does not need to infer prefill and decode performance from
one total request duration.

The initial measurement contract should preserve them separately.

### Initial measurement contract

012A supports recording the following request-level fields when exposed
by llama.cpp:

```text
prompt_tokens
completion_tokens
total_tokens
cached_tokens

prompt_evaluated_tokens
prompt_ms
prompt_per_token_ms
prompt_tokens_per_second

generated_tokens
generation_ms
generation_per_token_ms
generation_tokens_per_second

finish_reason
```

The initial runtime provenance should record at minimum:

```text
runtime = llama.cpp
runtime_commit
runtime_describe
runtime_version
runtime_build
system_fingerprint
```

The model provenance should record at minimum:

```text
model_id
quantization
```

The runtime configuration should record at minimum:

```text
threads
configured_context
temperature
max_tokens
```

### Terminology

Hewn should use the following terminology in its own measurement layer:

```text
prompt_tokens
completion_tokens
cached_prompt_tokens
prompt_evaluated_tokens

prompt_seconds
generation_seconds

prompt_tokens_per_second
generation_tokens_per_second
```

The harness may translate llama.cpp names such as:

```text
prompt_n
predicted_n
prompt_ms
predicted_ms
```

into this normalized representation while preserving the raw response.

### Wall time

012A does not promote HTTP wall time as a replacement for either prompt
or generation timing.

A later harness may record end-to-end wall time as an additional metric.

If recorded, it remains distinct from:

```text
prompt_seconds
generation_seconds
```

because request handling and other overhead may contribute to wall time.

### Memory

The inspected completion response does not expose process memory or peak
memory measurements.

Therefore memory is not yet part of the request-response measurement
contract.

A later experiment must establish a separate reliable measurement
mechanism before memory metrics are promoted.

### Artifact size

The completion response does not expose model artifact size.

Artifact size is model metadata rather than a request-level inference
measurement and must be measured separately.

### Configured context versus consumed context

The server was configured with:

```text
context = 4096
```

while this request consumed only a small prompt.

The response exposes prompt-token usage but does not imply that
`prompt_tokens` equals configured context capacity.

Hewn must preserve these as separate measurements:

```text
configured_context
actual_prompt_tokens
```

### What 012A establishes

For the inspected llama.cpp build, Hewn can obtain direct runtime
measurements for:

- total prompt tokens;
- completion tokens;
- cached prompt tokens;
- prompt tokens actually evaluated;
- prompt-processing latency;
- prompt-processing throughput;
- generated-token count;
- generation latency;
- generation throughput;
- completion termination reason;
- runtime fingerprint.

This is sufficient to justify building a reusable inference measurement
harness.

### What 012A does not establish

012A does not establish:

- stability of these timings across repeated runs;
- memory consumption;
- cold-start cost;
- model-loading cost;
- time to first generated token;
- whether caching behavior is stable across requests;
- thread-count optimality;
- context-length scaling;
- quantization tradeoffs;
- model-size tradeoffs;
- agent-level capability;
- compatibility of these fields across arbitrary llama.cpp versions.

The observations are scoped to the inspected runtime and request.

### Production decision

Proceed to 012B and build a small inference measurement harness around
the fields directly exposed by llama.cpp.

Do not estimate token counts from characters.

Do not collapse prompt processing and generation into one latency
measurement.

Do not infer memory consumption from GGUF file size.

Preserve raw runtime measurements alongside normalized measurements.

### Design principle

> Measure what the runtime actually did, not what the request looked
> like from outside.

## 012B — Reproducible inference measurement harness

### Research question

Can Hewn capture llama.cpp inference measurements in a reproducible,
machine-readable form without estimating information already exposed by
the runtime?

### Hypothesis

A small measurement harness can normalize llama.cpp request-level
telemetry while preserving the raw runtime response and enough
provenance to reproduce the run.

### Requirements

The harness must record three distinct categories.

#### Provenance

```text
runtime
runtime_commit
runtime_version
runtime_build
model_id
quantization
hardware_description
```

#### Configuration

```text
base_url
threads
configured_context
temperature
max_tokens
```

Configuration fields describe the server/request configuration supplied
by the caller. The harness must not infer server configuration that it
cannot observe.

#### Measurements

```text
prompt_tokens
completion_tokens
total_tokens
cached_prompt_tokens
prompt_evaluated_tokens

prompt_seconds
generation_seconds
prompt_tokens_per_second
generation_tokens_per_second

wall_time_seconds
finish_reason
```

The harness must preserve wall time separately from llama.cpp's internal
prompt and generation timings.

### Raw evidence

The complete JSON response returned by llama.cpp must be retained in the
run record.

Normalized fields are a convenience layer over the raw evidence, not a
replacement for it.

### Validation

When the relevant fields are available, the harness should validate:

```text
prompt_tokens + completion_tokens == total_tokens
```

and:

```text
cached_prompt_tokens + prompt_evaluated_tokens == prompt_tokens
```

and:

```text
generated_tokens == completion_tokens
```

A violated accounting invariant must be visible rather than silently
corrected.

### Timing conversion

llama.cpp reports prompt and generation timing in milliseconds.

Hewn should normalize those values to seconds while preserving the raw
response.

### Missing measurements

Missing runtime measurements must remain absent.

The harness must not estimate:

- token counts from characters;
- memory from model artifact size;
- prompt time from wall time;
- generation time from wall time.

### Experimental protocol

After implementation, run the same frozen request used in 012A through
the harness.

The purpose is not to reproduce identical timing values.

The experiment passes if:

1. the request completes;
2. the raw response is retained;
3. directly exposed measurements are normalized correctly;
4. accounting invariants pass;
5. wall time is measured separately;
6. provenance and caller-supplied configuration are retained.

### Non-goals

012B does not yet:

- measure peak memory;
- benchmark context scaling;
- benchmark thread scaling;
- compare quantizations;
- compare model sizes;
- integrate inference telemetry into Hewn Bench;
- provide a general provider abstraction.

### Decision rule

If the harness reliably captures the frozen fields without estimation,
use it for subsequent Module 12 experiments.

Otherwise, fix the measurement mechanism before collecting performance
results.