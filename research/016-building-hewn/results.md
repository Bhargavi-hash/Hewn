# Module 16 Results: Building Hewn

## Status

Complete through Module 16E.

Module 16 integrated the mechanisms developed in Modules 1–15 into the production Hewn agent and evaluated the resulting system on a frozen end-to-end repository benchmark.

The central production contract is:

> The model proposes intent. Hewn converts, validates, authorizes, executes, observes, and decides whether completion is allowed.

The strongest result from this module is not behavioral task success. The 0.5B model still fails the frozen end-to-end tasks. Instead, Module 16 established the production control boundaries, exposed an important conversation-representation inconsistency, and isolated a failure mode where deterministic tool bootstrapping causes valid action imitation rather than useful task progression.

---

## 16A: Semantic Action Normalization

### Question

Can Hewn safely recover a small number of semantically clear model actions that fail only because their representation differs from the canonical tool schema?

### Implementation

A narrow deterministic action normalizer was added at the model protocol boundary.

Accepted aliases were intentionally restricted to `read_file`:

    {"action":"read_file","file":"src/example.py"}

and:

    {"tool":"read_file","args":["src/example.py"]}

Both can be deterministically converted to the canonical typed action:

    {
      "type": "tool_call",
      "name": "read_file",
      "arguments": {
        "path": "src/example.py"
      }
    }

No tool selection, argument inference, edit repair, or semantic reasoning is performed by the normalizer.

### M15 post-hoc replay

The frozen Module 15 held-out recovery outputs were replayed through the normalizer.

| Metric | Result |
|---|---:|
| Evaluation rows | 32 |
| Strictly valid | 0 |
| Safely normalizable | 16 |
| Correct after normalization | 16 |
| Correct-after-normalization rate | 50% |

The recoverable cases came from the two families where Module 15 had already shown semantic `read_file` behavior but emitted the wrong schema:

- `failed_verification`: 8/8
- `missing_target`: 8/8

### Decision

Keep narrow deterministic representation repair.

Do not broaden normalization into model reasoning.

Strict protocol compliance and normalized compliance remain separate metrics.

---

## 16B: Canonical Protocol Provenance

### Question

Can Hewn distinguish native canonical model behavior from deterministic representation repair while preserving one production protocol?

### Implementation

Hewn now has:

- strict canonical parsing,
- canonical model-response serialization,
- explicit normalization provenance,
- model protocol diagnostics,
- raw-response preservation for protocol errors.

Canonical tool actions use:

    {
      "type": "tool_call",
      "name": "...",
      "arguments": {}
    }

Canonical final responses use:

    {
      "type": "final",
      "text": "..."
    }

### Protocol fixture

A deterministic protocol fixture contained 18 cases:

| Case type | Count |
|---|---:|
| Canonical | 4 |
| Safe aliases | 2 |
| Rejected | 12 |
| Correct classifications | 18/18 |

### Decision

Keep the strict canonical protocol as the production wire format.

Normalization provenance must remain visible rather than being counted as native protocol compliance.

The 18/18 result validates the deterministic protocol fixture only. It does not establish coding-agent capability.

---

## 16C: Frozen End-to-End Repository Benchmark

### Benchmark

A 12-task benchmark was frozen before the end-to-end model run.

It contains four task families with three tasks each:

- localized fixes,
- cross-file fixes,
- test-driven fixes,
- verification-required fixes.

Each task uses:

- a repository fixture,
- a hidden behavioral evaluator,
- regression tests,
- expected changed files.

Frozen benchmark commit:

    851de9e

### Model

    Qwen2.5-Coder-0.5B-Instruct

The production Hewn stack included:

- repository indexing,
- semantic retrieval,
- context construction,
- strict model protocol,
- action normalization,
- authority checks,
- tool execution,
- atomic editing,
- execution feedback,
- verification-gated completion,
- telemetry.

Maximum model turns:

    12

Completion requirement:

    VERIFIED

### Frozen baseline result

| Metric | Result |
|---|---:|
| Tasks | 12 |
| Behavioral successes | 0/12 |
| Hidden task oracle successes | 0/12 |
| Regression oracle successes | 9/12 |
| Stagnation terminations | 8 |
| Protocol-error terminations | 4 |
| Tasks reaching model-selected tool use | 0/12 |
| Tasks reaching execution | 0/12 |
| Canonical model responses | 24 |
| Normalized model responses | 0 |

The model never entered a useful tool/edit/verification loop on the frozen baseline.

Two runs reported changed files despite zero model-selected tools. These changes could not be attributed to model actions and are treated as measurement contamination rather than model edits.

### Decision

Preserve this run as the frozen historical 16C baseline.

Do not reinterpret the result after later production fixes.

---

## 16D: Local CLI and Package Integration

### Goal

Verify that the production Hewn stack can be invoked through the local CLI rather than only through research harnesses and unit tests.

### Result

The CLI successfully constructed the production session and reached the local model boundary.

A model-server availability preflight was added so a missing local server fails before expensive embedding-model initialization.

With the server running, the CLI progressed through retrieval and model inference but could still fail on invalid model protocol output.

The complete test suite after the 16D integration contained:

    274 passing tests

### Decision

The CLI integration is operational.

This is an integration result, not evidence of task-solving capability.

---

## 16E: Deterministic Repository Bootstrap Experiment

### Hypothesis

The 16C model already receives retrieved repository evidence in its initial context.

The experiment therefore did not test whether the model merely needs repository information.

Instead, it tested:

> Although Hewn already supplies retrieved repository evidence in the initial prompt, the 0.5B model may fail to transition from passive context to the tool-use loop. A single deterministic read-only controller bootstrap through the actual tool interface may improve progression into executable interaction.

### Treatment

The treatment performs exactly one controller-selected:

    repository_map {}

before the model's first decision.

The call passes through the real `ToolExecutor`, including schema and authority checks.

The resulting conversation is then passed to the normal Hewn agent loop.

The controller-selected bootstrap is measured separately and is not counted as a model-selected tool call.

No edit or verification action is forced.

---

## 16E-v1: Human-Readable Bootstrap Representation

The first treatment represented the synthetic assistant action as:

    Controller bootstrap tool call: repository_map {}

Across the instrumented runs, the model copied that representation as its first generation rather than producing canonical JSON.

For 11 instrumented tasks, the rejected generation was exactly:

    Controller bootstrap tool call: repository_map {}

The first `localized-001` run also failed at the first model response, but its raw generation had not yet been captured by the runner.

### Interpretation

This treatment was confounded by a novel noncanonical assistant-history representation.

It therefore does not establish whether repository bootstrap itself is useful or harmful.

The artifacts are retained as negative experimental evidence.

---

## 16E-v2: Canonical Bootstrap and Representation Bug Discovery

The bootstrap helper was changed to use the production canonical serializer.

An initial supposed v2 run was later found to still use the old helper path. That run is retained as a misconfigured artifact and is not counted as valid v2 evidence.

After the wiring was corrected and independently tested, the real canonical-bootstrap smoke produced:

    rejected_generation='Tool call: repository_map {}'

rather than canonical JSON.

This exposed a broader production inconsistency.

### Production inconsistency

Successfully parsed model tool actions were executed as typed `ToolCall`s, but Hewn then wrote them back into model-visible assistant history as:

    Tool call: <name> <arguments>

The model was therefore required to emit canonical JSON while being shown a different representation for previous assistant tool actions.

### Fix

Production assistant tool history now uses the same canonical serializer as the model protocol.

Human-readable action descriptions remain suitable for telemetry and UI, but not for model-visible conversation state.

The resulting invariant is:

> Every typed assistant action written into model-visible conversation history uses Hewn's canonical model protocol.

After this fix, the full test suite contained:

    275 passing tests

This production change means the original 16C run remains a historical baseline but is not a clean control for subsequent bootstrap experiments.

---

## 16E-v3: Post-Fix Paired Smoke Test

A new control and treatment were therefore run on the same production code using `localized-001`.

### Control

No deterministic bootstrap was supplied.

| Metric | Control |
|---|---:|
| Behavioral success | 0 |
| Hidden task success | 0 |
| Regression success | 1 |
| Terminal state | stagnation |
| Model attempts | 4 |
| Protocol rejections | 0 |
| Canonical responses | 4 |
| Model-selected tool calls | 1 |
| Execution checks | 0 |
| Changed files | 0 |
| Controller bootstrap calls | 0 |
| Wall time | 5.83 s |

The first model-selected action was `replace_text`, attempting to replace `test_slug_words` inside `src/sample/slug.py`.

The edit failed because the target text was not present.

After the failed edit, the model emitted final responses derived from the error and controller completion-rejection feedback. Hewn correctly refused completion because no successful verification had occurred.

The run terminated after three consecutive non-progressing turns.

### Bootstrap treatment

The treatment supplied one deterministic controller-selected `repository_map` observation before the model's first decision.

| Metric | Bootstrap |
|---|---:|
| Behavioral success | 0 |
| Hidden task success | 0 |
| Regression success | 1 |
| Terminal state | agent limit |
| Model attempts | 12 |
| Protocol rejections | 0 |
| Canonical responses | 12 |
| Model-selected tool calls | 12 |
| Execution checks | 0 |
| Changed files | 0 |
| Controller bootstrap calls | 1 |
| Bootstrap observation size | 151 chars |
| Wall time | 33.75 s |

Every model-selected action was:

    repository_map {}

The trajectory was therefore:

    controller repository_map
            ↓
    model repository_map
            ↓
    model repository_map
            ↓
    ...
            ↓
    model repository_map
            ↓
    12-turn agent limit

The model never transitioned to `search_text`, `read_file`, editing, or execution verification.

### Interpretation

The treatment dramatically increased syntactically valid and executable tool use from 1 model-selected tool call to 12, but did not increase useful task progress.

The additional calls were repeated imitation of the controller-provided action.

Therefore:

> More valid tool calls are not equivalent to better agent behavior.

The bootstrap treatment increased interaction quantity while reducing action diversity and did not improve behavioral correctness.

Because the paired smoke exposed a clear repetition mechanism, the remaining 11 tasks were not run under v3. Doing so would primarily spend additional inference on an already observed treatment failure rather than answering a new experimental question.

---

## Production Finding: Representation Consistency Matters

Module 16E produced an important result independent of the bootstrap hypothesis.

Before the production history fix, the historical `localized-001` run made zero model-selected tool calls.

After canonicalizing model-visible assistant tool history, the post-fix control produced one task-directed `replace_text` attempt.

This does not establish improved behavioral capability. Behavioral success remained 0.

It does show improved progression through the mechanical agent loop.

The result supports a production design rule:

> The protocol used for model output and the representation of previous assistant actions shown back to the model should be consistent.

This is especially important for small models, where representation differences can dominate behavior.

---

## What Module 16 Shows About the 0.5B Model

Across Modules 14–16, a consistent distinction has emerged.

The model can increasingly produce or imitate valid action structure, but reliable state-conditioned action selection remains weak.

Examples include:

- Module 14 learning protocol shape without held-out action correctness.
- Module 15 changing recovery-action semantics without producing reliable canonical executable actions.
- Module 16E producing twelve valid `repository_map` calls after seeing one controller-provided repository-map action.

The remaining problem is therefore not simply:

> Can the model use tools?

Hewn can induce valid tool use.

The harder problem is:

> Given the current repository and execution state, can the model choose the next useful action?

The `localized-001` control also exposes a separate recovery weakness:

    attempt edit
    → target missing
    → fail to gather new evidence
    → echo failure/completion feedback
    → stagnate

This is consistent with the recovery-policy limitations observed in Module 15.

---

## Decisions Carried Forward

### Keep

- deterministic repository indexing,
- semantic retrieval,
- bounded context construction,
- strict canonical model protocol,
- narrow deterministic action normalization,
- protocol provenance,
- typed tool calls,
- authority enforcement,
- structured read/search/edit/check tools,
- atomic edit semantics,
- normalized execution feedback,
- verification-gated completion,
- stagnation detection,
- persistent repository intelligence where appropriate,
- explicit telemetry and benchmark provenance,
- canonical model-visible assistant history.

### Reject or avoid

- broad semantic action repair,
- treating normalized output as native protocol compliance,
- model reviewers for mechanically decidable conditions,
- controller-injected repository-map bootstrap as tested in 16E,
- equating tool-call count with agent progress,
- silently changing frozen benchmark tasks after observing results.

### Still unresolved

- reliable state-conditioned tool selection for small models,
- recovery after failed edits,
- transition from repository evidence to grounded file inspection,
- transition from successful mutation to verification,
- whether a stronger local model materially changes these failure boundaries,
- whether targeted training can improve policy rather than only action representation.

---

## Module 16 Summary

Module 16 did not demonstrate that a 0.5B model can solve the frozen Hewn repository benchmark.

It did establish the integrated production architecture and identify where the current system fails.

The most important observations are:

1. Deterministic normalization can safely recover narrow representation errors without turning the controller into a second reasoning model.
2. Protocol provenance must distinguish native model compliance from controller repair.
3. The frozen 0.5B end-to-end baseline achieved 0/12 behavioral success and did not enter the tool loop.
4. Hewn's local CLI and production session can execute the integrated architecture end to end.
5. Model-visible assistant history originally violated Hewn's own canonical protocol. The bootstrap experiment exposed this integration defect.
6. Canonicalizing that history allowed the post-fix control smoke to reach a task-directed tool action, but behavioral correctness remained zero.
7. Deterministically bootstrapping the tool loop with `repository_map` caused twelve consecutive valid `repository_map` calls rather than useful repository navigation.
8. Valid tool syntax and high tool-call counts are insufficient measures of agent intelligence.

The current evidence therefore points toward state-conditioned action policy and recovery as the next major model-side bottlenecks, rather than basic repository retrieval or the mere ability to emit tool calls.

Module 17 should evaluate the frozen Hewn architecture against frontier coding agents without hiding these limitations.
