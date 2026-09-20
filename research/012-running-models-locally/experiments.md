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

### 012B result

The first live harness run completed successfully.

Observed normalized measurements:

```text
prompt_tokens = 47
cached_prompt_tokens = 46
prompt_evaluated_tokens = 1

completion_tokens = 17
generated_tokens = 17
total_tokens = 64

prompt_seconds = 0.097939
generation_seconds = 1.383797
wall_time_seconds = 1.585438

prompt_tokens_per_second = 10.210437
generation_tokens_per_second = 11.562390

finish_reason = stop
```

All observed accounting invariants passed:

```text
prompt_tokens + completion_tokens == total_tokens
47 + 17 == 64

cached_prompt_tokens + prompt_evaluated_tokens == prompt_tokens
46 + 1 == 47

generated_tokens == completion_tokens
17 == 17
```

The complete llama.cpp response was retained in the run record.

Runtime provenance and caller-supplied inference configuration were also
retained.

#### Important cache observation

This run reused almost the complete prompt:

```text
46 / 47 prompt tokens cached
1 / 47 prompt tokens evaluated
```

Therefore the observed:

```text
prompt_tokens_per_second = 10.210437
```

must not be interpreted as representative full-prompt prefill
throughput.

It measures a request for which only one prompt token required
evaluation.

This demonstrates that later latency experiments must explicitly control
or record prompt-cache state.

The harness already preserves enough information to identify this case
because it records total, cached, and evaluated prompt tokens separately.

#### Wall-time observation

For this run:

```text
internal prompt time      = 0.097939 s
internal generation time  = 1.383797 s
sum                       = 1.481736 s
wall time                 = 1.585438 s
```

The difference is approximately:

```text
0.103702 s
```

This is consistent with the design decision to preserve wall time
separately from llama.cpp's internal prompt and generation measurements.

A single run does not establish the source or stability of that
difference.

#### Experimental outcome

012B passes its frozen decision rule:

1. the request completed;
2. the raw response was retained;
3. directly exposed measurements were normalized;
4. all observed accounting invariants passed;
5. wall time was recorded separately;
6. provenance and caller-supplied configuration were retained.

The measurement harness is therefore retained for subsequent Module 12
experiments.

#### Production decision

Keep the measurement harness.

Do not estimate token counts from characters.

Do not merge prompt and generation latency.

Do not interpret prompt throughput without examining:

```text
prompt_tokens
cached_prompt_tokens
prompt_evaluated_tokens
```

Subsequent performance experiments must control prompt caching or make
cache state an explicit experimental variable.

## 012C — Prompt-cache behavior

### Research question

How does llama.cpp prompt caching change the amount of prompt work
performed for repeated requests, and what measurement protocol should
later Module 12 performance experiments use?

### Motivation

012B observed the following repeated-prompt request:

```text
prompt_tokens = 47
cached_prompt_tokens = 46
prompt_evaluated_tokens = 1
```

Only one of 47 logical prompt tokens was evaluated.

Therefore prompt-cache state is a potential confounder for latency and
throughput experiments.

Before context, thread, quantization, or model-size comparisons, Hewn
must establish how prompt caching will be handled.

### Runtime controls discovered

The inspected llama.cpp build exposes:

```text
--cache-prompt
--no-cache-prompt
```

with prompt caching enabled by default.

It also exposes related controls including:

```text
--cache-reuse
--cache-idle-slots
--slot-prompt-similarity
--parallel
--slots
```

012C does not attempt to characterize all of these mechanisms.

The controlled variable in this experiment is only whether prompt
caching is enabled.

### Important distinction

012C distinguishes prompt reuse from other caches and memory mechanisms,
including:

```text
KV cache datatype
SWA cache
speculative decoding caches
model artifact cache
operating-system page cache
```

Those mechanisms are outside the scope of this experiment.

### Frozen model

```text
Qwen/Qwen2.5-Coder-1.5B-Instruct-GGUF:Q4_K_M
```

### Frozen runtime

```text
llama.cpp commit:
930e2fa5995789efbf249a8bf61325bb626e417b

build:
10991

threads:
4

configured context:
4096

temperature:
0

max completion tokens:
64
```

### Frozen prompt

```text
Write a Python function add(a, b) that returns the sum of a and b.
```

### Conditions

Two server conditions will be compared.

#### Condition A — Prompt caching enabled

Start the server with:

```text
--cache-prompt
```

Run the identical frozen request three times sequentially.

#### Condition B — Prompt caching disabled

Start a fresh server with:

```text
--no-cache-prompt
```

Run the identical frozen request three times sequentially.

### Measurements

For every request record:

```text
prompt_tokens
cached_prompt_tokens
prompt_evaluated_tokens
prompt_seconds
prompt_tokens_per_second

completion_tokens
generation_seconds
generation_tokens_per_second

wall_time_seconds
```

The experiment focuses primarily on:

```text
cached_prompt_tokens
prompt_evaluated_tokens
```

because those fields directly describe how much prompt work llama.cpp
reports performing.

### Primary expectation

With prompt caching enabled, later identical requests may reuse most of
the prompt.

With prompt caching disabled, repeated requests should require
substantially more prompt evaluation.

This expectation is tested rather than assumed.

### Interpretation rule

Prompt throughput is interpreted together with the number of prompt
tokens actually evaluated.

For example, throughput measured from one evaluated token must not be
directly compared with throughput measured from a full prompt as though
they represented equivalent work.

### Performance protocol decision

If `--no-cache-prompt` prevents repeated-request prompt reuse reliably,
later controlled inference-performance experiments will use:

```text
--no-cache-prompt
```

unless prompt caching itself is the experimental variable.

This provides comparable request-level prompt work without requiring a
server restart between every repetition.

### Non-goals

012C does not attempt to measure:

- cold model loading;
- operating-system page-cache effects;
- KV-cache datatype effects;
- continuous batching;
- multiple simultaneous slots;
- production throughput under repeated workloads;
- whether prompt caching is desirable in normal Hewn operation.

The experiment is about benchmark control, not production policy.

### Decision rule

Adopt `--no-cache-prompt` for subsequent controlled latency experiments
if repeated requests under that condition consistently report no
substantial prompt reuse.

Otherwise, establish a stronger cache-isolation procedure before
continuing with performance experiments.

### 012C results

Six runs were collected: three with prompt caching explicitly enabled
and three with prompt caching explicitly disabled.

All requests used the same model, prompt, thread count, configured
context, temperature, and completion limit.

### Observed measurements

```text
condition   run   prompt   cached   evaluated   prompt_ms   prompt_tok/s
cache-on      1       47       46           1      83.595         11.962
cache-on      2       47       46           1      86.065         11.619
cache-on      3       47       46           1      75.004         13.333

cache-off     1       47        0          47     953.092         49.313
cache-off     2       47        0          47     918.768         51.155
cache-off     3       47        0          47    1298.063         36.208
```

Generation measurements were:

```text
condition   run   completion   generation_ms   generation_tok/s   wall_s
cache-on      1           17        1311.248             12.202    1.403
cache-on      2           17        1348.154             11.868    1.446
cache-on      3           17        1204.202             13.287    1.293

cache-off     1           17        1559.884             10.257    2.524
cache-off     2           17        1352.035             11.834    2.282
cache-off     3           17        1258.163             12.717    2.568
```

### Prompt reuse

With prompt caching enabled, every observed request reported:

```text
prompt_tokens = 47
cached_prompt_tokens = 46
prompt_evaluated_tokens = 1
```

With prompt caching disabled, every observed request reported:

```text
prompt_tokens = 47
cached_prompt_tokens = 0
prompt_evaluated_tokens = 47
```

Therefore, in this three-run diagnostic, `--no-cache-prompt`
successfully prevented the substantial repeated-prompt reuse observed
with prompt caching enabled.

### Throughput interpretation

Prompt throughput cannot be interpreted independently from the number
of evaluated tokens.

For the cache-enabled runs, llama.cpp calculated prompt throughput from
only one evaluated prompt token.

Those values therefore do not represent full-prompt prefill throughput
and should not be directly compared with the cache-disabled 47-token
prefill measurements as equivalent workloads.

### Timing observation

Prompt caching substantially reduced observed prompt-processing time in
these repeated requests because almost the entire prompt was reused.

The experiment does not estimate the general latency benefit of prompt
caching.

Generation throughput also varied across repetitions even though the
generated token count remained 17.

Therefore later timing experiments should use repeated observations
rather than treating a single timing measurement as representative.

### Decision

The frozen decision rule is satisfied.

Across all three cache-disabled repetitions:

```text
cached_prompt_tokens = 0
prompt_evaluated_tokens = prompt_tokens = 47
```

Subsequent controlled Module 12 inference-performance experiments will
therefore run llama.cpp with:

```text
--no-cache-prompt
```

unless prompt caching itself is the experimental variable.

This is a benchmark-control decision.

It is not a production recommendation for Hewn.

### What 012C establishes

For this llama.cpp build, model, and three-run diagnostic:

1. repeated requests with prompt caching enabled can reuse nearly the
   entire prompt;
2. prompt reuse materially changes the amount of prompt evaluation
   performed;
3. prompt throughput must be interpreted relative to evaluated prompt
   tokens;
4. `--no-cache-prompt` prevented substantial prompt reuse in all three
   observed cache-disabled runs;
5. disabling prompt caching provides a suitable control protocol for
   subsequent request-level inference comparisons.

### What 012C does not establish

012C does not establish:

- the general production benefit of prompt caching;
- cache behavior under multiple concurrent slots;
- cache behavior for partially shared prompts;
- cache behavior across arbitrary llama.cpp versions;
- cold model-loading performance;
- operating-system page-cache behavior;
- whether prompt caching should be disabled in normal Hewn operation.

### Benchmark protocol update

For subsequent controlled inference experiments:

```text
prompt caching = disabled
```

Every run must still record:

```text
prompt_tokens
cached_prompt_tokens
prompt_evaluated_tokens
```

A run showing unexpected prompt reuse should remain visible and should
not silently enter an uncached-performance aggregate.

## 012D — CPU thread scaling

### Research question

How does llama.cpp CPU thread count affect uncached prompt processing
and autoregressive generation on the fixed Hewn development machine?

### Motivation

The existing Hewn llama.cpp configuration uses:

```text
threads = 4
```

This value was inherited from the initial development setup rather than
selected through measurement.

The machine has:

```text
4 physical CPU cores
8 logical CPU threads
```

Thread count may affect prompt processing and autoregressive generation
differently.

If thread count is not controlled, it can confound later context,
quantization, and model-size experiments.

### Hypothesis

Prompt processing and autoregressive decoding will not necessarily have
the same thread-scaling behavior.

Increasing thread count may improve throughput up to some point, but
additional logical threads are not assumed to improve either workload.

### Frozen hardware

```text
CPU:
Intel Core i5-10210U

physical cores:
4

logical threads:
8

RAM:
approximately 7.6 GiB

inference:
CPU
```

### Frozen runtime

```text
llama.cpp commit:
930e2fa5995789efbf249a8bf61325bb626e417b

build:
10991

prompt caching:
disabled

configured context:
4096
```

### Frozen model

```text
Qwen/Qwen2.5-Coder-1.5B-Instruct-GGUF:Q4_K_M
```

### Experimental variable

The only intended server-level variable is:

```text
threads
```

Conditions:

```text
1
2
4
8
```

### Prompt workload

The thread-scaling experiment should use a fixed prompt substantially
larger than the 47-token instrumentation prompt used in 012A–012C.

The prompt must be generated deterministically and frozen before thread
scaling results are observed.

Target:

```text
approximately 512 actual prompt tokens
```

The actual token count reported by llama.cpp is authoritative.

The experiment does not require exactly 512 tokens.

### Generation workload

Use:

```text
max_tokens = 128
temperature = 0
```

The actual generated-token count must be recorded for every run.

Generation throughput comparisons must account for differing generated
token counts or early termination.

### Repetitions

Run:

```text
5 repetitions per thread condition
```

for:

```text
4 thread conditions × 5 repetitions = 20 runs
```

Every run remains individually inspectable.

### Cache control

All servers must use:

```text
--no-cache-prompt
```

Every run must additionally satisfy:

```text
cached_prompt_tokens = 0
prompt_evaluated_tokens = prompt_tokens
```

A run violating this condition remains in the raw results but is not
treated as an uncached measurement.

### Primary measurements

For prompt processing:

```text
prompt_evaluated_tokens
prompt_seconds
prompt_tokens_per_second
```

For generation:

```text
generated_tokens
generation_seconds
generation_tokens_per_second
```

Additional measurements:

```text
wall_time_seconds
```

### Aggregation

For each thread condition, report individual observations plus:

```text
minimum
median
maximum
```

for:

```text
prompt_tokens_per_second
generation_tokens_per_second
wall_time_seconds
```

The median is the primary descriptive timing statistic for this
experiment.

No statistical significance claim is made from five repetitions.

### Comparison rule

Prompt throughput and generation throughput remain separate.

Do not select a thread count by averaging the two throughput values.

If one configuration improves prompt processing while another improves
generation, report the tradeoff explicitly.

### Decision rule

A thread configuration may become the baseline for later Module 12
experiments if it provides a reasonable measured operating point for
both prompt processing and generation on this machine.

The decision must be based on observed measurements rather than the
number of physical or logical CPU threads alone.

### Non-goals

012D does not establish:

- universal optimal llama.cpp thread count;
- behavior on other CPUs;
- GPU inference behavior;
- concurrent-request throughput;
- production prompt-cache policy;
- context scaling;
- quantization scaling;
- model-size scaling;
- coding-agent behavioral capability.

### Interpretation scope

All conclusions are scoped to:

```text
this hardware
this llama.cpp build
this model
this quantization
this workload
this five-repetition experiment
```

### Workload token probe

Before observing any thread-scaling results, the frozen workload was
measured using the cache-disabled 4-thread baseline.

Observed:

```text
prompt_tokens = 321
cached_prompt_tokens = 0
prompt_evaluated_tokens = 321
prompt_seconds = 5.718660
prompt_tokens_per_second = 56.132031