## 011B — Repeated-run stability

### Question

How much can coding-agent outcomes vary across repeated runs when the
task, repository state, model configuration, agent configuration, and
nominal decoding settings are held fixed?

### Configuration

- Model: Qwen2.5-Coder-1.5B-Instruct
- Quantization: Q4_K_M
- Runtime: llama.cpp
- Temperature: 0
- Context window: 4096
- Threads: 4
- Repetitions: 5 per task
- Tasks: 3
- Total runs: 15
- Completion requirement: VERIFIED

Each repetition used a freshly recreated fixture repository and fresh
Hewn session. No persistent memory was shared between repetitions.

### Evaluator correction

The first execution, `011b-repeated-stability-run001.json`, was
preserved but invalidated for primary interpretation.

Its stability-002 regression oracle executed `client.py` outside the
fixture package environment and therefore produced:

`ModuleNotFoundError: No module named 'sample'`

The evaluator also approximated the stability-002 behavior oracle by
checking the constant and source text rather than executing
`request_policy()`.

Before run002:

1. hidden behavioral and regression oracles were moved behind Hewn's
   Bubblewrap execution boundary;
2. stability-002 was changed to execute both `DEFAULT_RETRIES` and
   `request_policy()`;
3. valid parsed model responses were recorded even when the overall
   agent run later terminated through stagnation or protocol failure.

No task request, fixture, model configuration, retrieval policy, tool
policy, completion requirement, or maximum-turn setting was changed.

The corrected untouched fixtures were validated before run002:

- stability-001: task false, regression true
- stability-002: task false, regression true, structural true
- stability-003: task false, regression true

Run002 is therefore the primary 011B result.

### Results

| Task | Behavioral success | Protocol valid | Runs with edits | Model calls | Tool calls |
|---|---:|---:|---:|---:|---:|
| stability-001 | 0/5 | 0/5 | 0/5 | 2–2 | 0–0 |
| stability-002 | 0/5 | 5/5 | 0/5 | 3–3 | 0–0 |
| stability-003 | 0/5 | 5/5 | 0/5 | 3–3 | 0–0 |
| Overall | 0/15 | 10/15 | 0/15 | — | 0 |

Observed wall-time ranges:

- stability-001: 4.53–5.61 s
- stability-002: 8.00–10.23 s
- stability-003: 5.78–8.95 s

All 15 runs produced the empty repository diff.

### Failure mechanism

The repeated outcomes were not failures after attempting repository
edits. The model never invoked a tool in any of the 15 runs.

For stability-001, every repetition first returned the proposed code as
a `FinalResponse`:

`FinalResponse(text="def greeting():\n    return 'hi'")`

Hewn rejected completion because successful verification had not been
observed. The next model response wrapped a final response in
`<tool_response>...</tool_response>`, which violated the required JSON
protocol. All five repetitions therefore terminated with protocol
failure after two model calls.

For stability-002, every repetition first returned a `FinalResponse`
claiming that the retry-count change had already been made even though
no repository mutation had occurred. After Hewn rejected premature
completion, the next two responses were also final responses stating
that completion could not occur without verification. All five runs
terminated through stagnation after three model calls.

For stability-003, every repetition initially returned
`FinalResponse(text='None')`. The following two responses again
attempted finalization rather than using tools, and all five runs
terminated through stagnation.

### Interpretation

On these three frozen tasks and this model configuration, repeated runs
did not reveal behavioral-success variability. Each task produced the
same success/failure classification in all five repetitions.

This is stability of the observed outcome, not evidence of general
determinism. Five identical repetitions cannot establish deterministic
behavior.

The experiment also demonstrates why protocol compliance must not be
treated as coding-task success. Ten of fifteen runs were protocol-valid,
but none satisfied the requested behavior. In this diagnostic,
protocol-valid final responses could describe or claim a change without
causing any repository mutation.

No patch variability was measurable because no run produced a patch.
The single observed diff hash corresponds to the empty diff and should
not be interpreted as evidence that generated patches were consistent.

The immediate observed failure occurred at the model-to-agent action
boundary: the model repeatedly selected finalization rather than
available repository tools. Edit application, execution feedback, and
patch verification were therefore never exercised by these runs.

This identifies a failure mechanism for this model/task configuration.
It does not establish that action selection is the dominant bottleneck
for coding agents generally.

### Conclusion

011B supports the evaluation methodology's requirement to report
behavioral correctness separately from protocol compliance and other
mechanical signals.

Repeated trials were also useful even though they did not expose
success variability. They showed that the observed failure modes
themselves were stable across five repetitions per task:

- stable protocol failure on stability-001;
- stable protocol-valid stagnation on stability-002;
- stable protocol-valid stagnation on stability-003.

A repeated failure is evidence about observed stability, not evidence
of capability.

The primary 011B artifact is:

`results/011b-repeated-stability-run002.json`

`run001` remains preserved as provenance for the evaluator correction.

## 011C — Regression-aware scoring

### Question

Can task-local verification incorrectly classify a patch as successful
when the requested behavior passes but existing behavior outside the
requested change regresses?

### Method

011C used four deterministic evaluator-authored candidate
implementations. No language model was involved.

Two scoring rules were compared:

```text
task_only_success = task_passes
```

and:

```text
behavioral_success = task_passes AND regression_passes
```

The task oracle checked the requested `normalize_name` behavior.

A separate evaluator-only regression oracle checked the existing
`stable_identifier` behavior.

### Results

| Condition | Task passes | Regression passes | Task-only success | Behavioral success |
|---|---:|---:|---:|---:|
| A — no-op | false | true | false | false |
| B — task correct, regression introduced | true | false | true | false |
| C — task wrong, regression preserved | false | true | false | false |
| D — task correct, regression preserved | true | true | true | true |

The observed matrix matched the frozen expected matrix:

```text
expected matrix matched: 4/4
task-only successes: 2/4
behavioral successes: 1/4
task-only false successes: 1
```

### False-success case

Condition B satisfied every requested-behavior assertion:

```text
normalize_name(" Alice ") == "alice"
normalize_name(" BOB ") == "bob"
normalize_name("   ") is None
```

Task-only scoring therefore classified the condition as successful.

However, the candidate also changed the existing behavior of
`stable_identifier`, causing the regression oracle to fail.

Regression-aware behavioral scoring therefore rejected the candidate.

This is the false-success case the frozen experiment was designed to
detect.

### Interpretation

011C demonstrates that task-local correctness and regression
correctness are distinct evaluation properties.

In this deliberately constructed diagnostic, a task-only evaluator
accepted one candidate that violated existing behavior. Requiring both
the task oracle and the regression oracle removed that false success
while preserving the fully correct condition D as successful.

This does not estimate the frequency with which coding agents introduce
regressions. The experiment intentionally contains one regression case
in four conditions.

It also does not show that a passing regression suite proves absence of
all regressions. The evaluator checks only the frozen behaviors included
in its regression oracle.

The result instead validates a benchmark-design requirement:

> Passing the requested task oracle is necessary but not sufficient for
> behavioral success when preservation requirements exist.

### Conclusion

For Hewn Bench, primary behavioral success should require both:

1. requested behavior passes;
2. required regression checks pass.

Task correctness and regression correctness should also remain available
as separate diagnostic fields so that a benchmark can distinguish:

- failure to implement the requested behavior;
- successful implementation with a regression;
- successful implementation without detected regression.

No weighted score is needed for this classification. Passing one
correctness dimension must not compensate for failing the other.

The primary 011C artifact is:

`results/011c-regression-aware-scoring-run001.json`

## 011D — Efficiency accounting

### Question

Can Hewn Bench account for the additional computational and interaction
cost of an agent strategy without allowing lower cost to compensate for
incorrect behavior or higher cost to masquerade as greater capability?

### Method

011D used four deterministic synthetic run records.

No language model was invoked. The experiment validates the accounting
and comparison rules rather than measuring the real efficiency of a
Hewn configuration.

Each run recorded:

- model calls;
- tool calls;
- execution calls;
- context characters;
- wall time.

Correctness was represented independently by `behavioral_success`.

No combined quality/cost score was used.

### Results

| Condition | Behavioral class | Model calls | Tool calls | Execution calls | Context chars | Wall time |
|---|---|---:|---:|---:|---:|---:|
| A — correct, lower cost | successful | 2 | 2 | 1 | 1000 | 4.0 s |
| B — correct, higher cost | successful | 5 | 6 | 3 | 3000 | 12.0 s |
| C — incorrect, lower cost | unsuccessful | 1 | 0 | 0 | 500 | 2.0 s |
| D — incorrect, higher cost | unsuccessful | 4 | 5 | 2 | 2500 | 10.0 s |

All four behavioral classifications matched the frozen expectations.

### Resource accounting

Across all four records:

```text
model_calls = 12
tool_calls = 13
execution_calls = 6
context_chars = 7000
wall_time_seconds = 28.0
```

Arithmetic means were:

```text
model_calls = 3.0
tool_calls = 3.25
execution_calls = 1.5
context_chars = 1750.0
wall_time_seconds = 7.0
```

Successful-run totals were:

```text
model_calls = 7
tool_calls = 8
execution_calls = 4
context_chars = 4000
wall_time_seconds = 16.0
```

Unsuccessful-run totals were:

```text
model_calls = 5
tool_calls = 5
execution_calls = 2
context_chars = 3000
wall_time_seconds = 12.0
```

The observed accounting matched every frozen expected aggregate.

### Resource dominance

011D defines resource dominance only between runs with the same
behavioral classification.

A run resource-dominates another run when it uses no more of every
measured resource and strictly less of at least one.

Observed:

```text
A dominates B within successful class: true
C dominates D within unsuccessful class: true
C dominates A across correctness classes: not evaluated
```

The final comparison is intentionally undefined rather than false.

C consumes fewer resources than A, but C is behaviorally unsuccessful
while A is successful. The resource relation therefore does not apply
across those correctness classes.

This prevents lower-cost failure from being interpreted as superior to
a successful solution.

### Interpretation

011D validates the separation between correctness and efficiency.

The benchmark should first ask:

```text
Did the agent solve the requested task without a detected regression?
```

It can then ask:

```text
What resources did the agent consume to obtain that outcome?
```

Resource measurements explain the cost of an outcome. They do not
change the correctness classification.

This distinction is important for mechanisms such as planning,
reviewing, retrieval, repair, and execution feedback. Adding such a
mechanism may increase model calls, context, tool usage, execution, or
latency. Those additional costs should be visible even when behavioral
success improves, remains unchanged, or decreases.

Likewise, an inexpensive failure should remain a failure.

### Measurement limitations

The synthetic records do not establish that any real Hewn strategy is
faster or cheaper.

The measured dimensions are also not interchangeable:

- model calls can have different inference costs;
- tool calls can perform different amounts of work;
- execution calls can have different runtimes;
- context characters are not tokenizer-level token counts;
- wall time depends on hardware and runtime conditions.

011D therefore does not justify collapsing these dimensions into one
universal efficiency score.

Token usage was deliberately omitted because the current model
interface does not expose a uniform measured token-usage field.
Character counts were not converted into estimated tokens.

### Conclusion

Hewn Bench should preserve correctness and efficiency as separate
measurement dimensions.

Primary behavioral success should not contain a cost adjustment.

Raw efficiency fields should remain available for comparison, and
resource dominance should only be interpreted within equivalent
behavioral outcome classes unless correctness is explicitly reported
alongside the resource comparison.

The primary 011D artifact is:

`results/011d-efficiency-accounting-run001.json`

## 011E — Benchmark integrity and contamination

### Question

Can Hewn Bench mechanically separate agent-visible task information from
evaluator-only information so that hidden oracles, expected outputs, and
benchmark metadata cannot accidentally become part of the agent's
evaluation context?

### Method

011E used a deterministic synthetic benchmark case divided into two
representations:

```text
AgentVisibleCase
EvaluatorOnlyCase
```

The agent-visible representation contained:

- task request;
- repository context;
- available tool names.

The evaluator-only representation contained:

- behavioral assertions;
- regression assertions;
- expected changed files;
- expected patch markers;
- scoring metadata.

The payload builder accepted only the agent-visible representation.

Four assembly conditions were evaluated:

1. clean payload;
2. payload contaminated with a hidden behavioral assertion;
3. payload contaminated with an expected patch marker;
4. payload contaminated with hidden scoring metadata.

No language model was invoked.

### Results

| Condition | Payload constructed | Hidden markers exposed | Integrity passes |
|---|---:|---:|---:|
| A — clean | true | false | true |
| B — hidden oracle | true | true | false |
| C — expected patch | true | true | false |
| D — scoring metadata | true | true | false |

The observed matrix matched the frozen expected matrix:

```text
expected matrix matched: 4/4
clean payloads: 1/4
contaminated payloads detected: 3/3
false contamination detections on clean payload: 0
```

### Detected contamination

Condition B exposed:

```text
normalize_name(" Alice ") == "alice"
```

Condition C exposed:

```text
return normalized.lower()
```

Condition D exposed:

```text
primary_success = task_passes AND regression_passes
```

All three were rejected by the integrity classification.

The clean condition exposed none of the frozen hidden markers.

### Expected-file namespace check

The raw repository path:

```text
src/sample/normalization.py
```

was visible in the clean agent payload.

This is legitimate repository information and was not classified as
contamination.

The evaluator-specific marker:

```text
src/sample/normalization.py::expected_changed_file
```

was not visible.

Observed:

```text
raw expected path visible as legitimate repository context: true
namespaced expected-file marker visible: false
```

This distinction matters because information overlap alone does not
establish benchmark leakage. An agent may legitimately know that a file
exists while remaining unaware that the evaluator expects that file to
change.

### Interpretation

011E validates an explicit representation boundary between information
used to run an agent and information used to score it.

For this frozen diagnostic, direct exposure of benchmark-owned hidden
information was detected in all three deliberately contaminated
payloads, while the clean payload was not falsely rejected.

This does not prove absence of every form of benchmark contamination.

The detector operates on exact frozen markers. It does not detect:

- semantic paraphrases of hidden information;
- indirect hints;
- information memorized during model training;
- leakage through external systems;
- equivalent information expressed in an unrecognized representation.

The experiment therefore validates a benchmark-construction mechanism,
not a general contamination detector.

### Design implication

Hewn Bench should maintain an explicit structure equivalent to:

```text
BenchmarkCase
├── agent_visible
│   ├── task
│   ├── repository/context
│   └── allowed tool interface
└── evaluator_only
    ├── task oracle
    ├── regression oracle
    ├── structural oracle
    ├── expected-change metadata
    └── scoring metadata
```

Only `agent_visible` information should participate in agent-input
construction.

`evaluator_only` information should become available only to post-run
evaluation and diagnostics.

The type boundary alone should not be described as a security boundary.
Production benchmark construction should also validate the assembled
payload before execution.

### Conclusion

011E supports explicit separation of agent-visible and evaluator-only
benchmark information.

It also shows why contamination checks need provenance and semantics
around fields rather than raw string overlap alone. A repository path
may legitimately appear in both repository evidence and evaluator
metadata without the evaluator-specific meaning being disclosed.

The primary 011E artifact is:

`results/011e-benchmark-integrity-run001.json`