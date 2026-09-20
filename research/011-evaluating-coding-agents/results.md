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