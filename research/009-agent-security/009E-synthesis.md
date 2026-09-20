# 009E — Module 9 Security Synthesis

## Question

Which security mechanisms tested in Module 9 have earned promotion into
Hewn's production architecture, and which should remain research-only or
deferred?

## Security model

Hewn treats the following as untrusted:

- model output;
- repository-controlled content;
- tool arguments;
- instructions discovered inside repository files.

Authority is granted by the Hewn runtime, not by the model or repository.

The core invariant is:

> The model proposes actions. Hewn decides whether those actions are
> authorized.

Protocol validity, tool-schema validity, and authority are separate checks.

A response may therefore be:

1. syntactically valid;
2. valid for a tool schema;
3. still unauthorized for the current agent session.

## Evidence

### 009A — Workspace confinement

The frozen path corpus tested:

- legitimate repository paths;
- parent traversal;
- normalized internal paths;
- absolute paths;
- sibling-prefix escapes;
- internal symlinks;
- external symlinks;
- external-symlink descendants.

The existing `Workspace.resolve()` implementation matched all 11 frozen
expectations:

- authorized cases accepted: 4/4;
- unauthorized cases rejected: 7/7;
- false accepts: 0;
- false rejects: 0.

### Decision

Keep the existing canonical-path workspace confinement.

No additional production path-security abstraction was earned by this
experiment.

This result is scoped to the frozen path corpus and does not establish
general filesystem security.

---

### 009B — Command and transitive process authority

The existing `run_check` interface successfully prevented direct model
selection of:

- arbitrary commands;
- arbitrary paths;
- arbitrary environment variables.

The strict tool schema rejected all four frozen interface attacks.

However, once an approved check was executed normally, repository-controlled
code inherited the authority of the Hewn process.

The baseline demonstrated that approved pytest execution could:

- read outside the workspace;
- write outside the workspace;
- read inherited environment data;
- spawn a child process that read outside the workspace.

All four frozen transitive effects occurred.

A narrowly scoped Linux Bubblewrap intervention prevented all four tested
effects while preserving all three approved development checks.

### Decision

Keep the narrow `run_check` command vocabulary and strict schema.

Treat command authorization and process isolation as separate controls.

The Bubblewrap result establishes feasibility, but the research wrapper is
not automatically production-ready. Production sandbox integration requires
an explicit execution backend with a documented fallback policy.

Process isolation should therefore be represented as a separate execution
boundary rather than embedded inside task authority.

---

### 009C — Repository prompt injection

Repository-controlled instructions caused one model proposal to exceed the
authority implied by the frozen user task.

Without task authority:

- unauthorized proposals: 1;
- unauthorized executions: 1;
- unauthorized effects: 1.

With deterministic frozen task authority:

- unauthorized proposals: 1;
- policy rejections: 1;
- unauthorized executions: 0;
- unauthorized effects: 0.

The model remained compromised in the relevant case. The runtime prevented
the proposal from becoming an effect.

Task completion remained 3/5 in both conditions.

### Decision

Do not treat prompt engineering as the primary security boundary.

Introduce deterministic authorization between model proposal and tool
execution.

Repository content may influence reasoning but must not grant operational
authority.

A schema-valid `ToolCall` is not necessarily an authorized `ToolCall`.

---

### 009D — Authority granularity and utility

After the frozen outer-fence representation normalization removed the
observed protocol floor:

- unrestricted authority: 0/5 task success;
- capability authority: 0/5 task success;
- exact-resource authority: 0/5 task success.

Conditions A and B produced the same observed tool behavior.

No observed utility penalty from capability-level authority relative to
unrestricted authority was demonstrated in this five-task single run.

Exact-resource authority prevented one task-unnecessary approved check from
executing, but also rejected one legitimate repository-discovery action.

Because unrestricted authority itself achieved 0/5 task success, the run
cannot quantify an end-to-end task-success cost caused by authority
restriction.

### Decision

Do not promote evaluator-known exact-resource authority into production.

It assumes knowledge of the resources needed to solve the task while
potentially denying the discovery operations needed to locate those
resources.

Capability-level authority is the current production candidate.

The experiment does not establish that capability authority is universally
utility-preserving. It establishes only that this frozen diagnostic produced
no observed utility difference relative to unrestricted tools.

---

## Production architecture

The production action path should become:

    Model
      |
      v
    ModelProtocol parser
      |
      v
    ToolCall
      |
      v
    Tool schema validation
      |
      v
    AuthorityPolicy
      |
      +---- denied ----> visible rejection observation
      |
      v
    Tool handler
      |
      v
    execution / verification

For process-capable tools:

    authorized ToolCall
      |
      v
    ProcessExecutionBackend
      |
      +---- isolated backend
      |
      +---- explicitly configured fallback
      |
      v
    subprocess

Authority and isolation remain separate abstractions.

## Production authority representation

The initial production policy should operate at capability granularity.

Candidate capabilities:

- repository observation;
- repository mutation;
- approved development checks.

The policy must not contain:

- hidden evaluator solution files;
- model-generated authority grants;
- repository-generated authority grants;
- arbitrary shell authority;
- arbitrary environment authority;
- arbitrary external-filesystem authority.

Workspace confinement remains an independent lower-level invariant for
filesystem tools.

## Initial session grant

The first production implementation should use an explicit immutable session
grant.

Conceptually:

    AuthorityGrant(
        repository_read=True,
        repository_write=True,
        approved_checks=True,
    )

The grant is created by trusted Hewn runtime configuration.

It is not inferred from repository text.

The initial implementation should not attempt to solve natural-language
least-privilege inference.

That problem remains open.

## Denial semantics

An authority denial must:

1. occur before the tool handler executes;
2. produce no tool side effect;
3. be returned to the model as a visible tool observation;
4. identify the denied capability;
5. avoid silently changing the requested action.

The model may then choose another action.

Authority rejection is therefore part of the agent feedback loop, not an
exception that terminates the process by default.

## What is promoted

### Promote now

- existing `Workspace.resolve()` confinement;
- existing strict tool schemas;
- existing narrow approved-check vocabulary;
- explicit capability classification;
- immutable runtime authority grant;
- deterministic `AuthorityPolicy`;
- authorization before tool handler execution;
- visible authority-denial feedback.

### Prototype separately

- Linux Bubblewrap-backed process execution.

The Module 9 result justifies an isolation backend prototype, but not yet a
claim of portable or production-complete sandboxing.

### Keep research-only

- frozen exact-resource oracle policy;
- 009C task-specific authority oracle;
- 009D-P Markdown-fence normalization.

The protocol normalizer was introduced only to remove an experimental
representation confounder. It does not change Hewn's production model
protocol.

### Defer

- natural-language authority inference;
- per-file dynamic least privilege;
- automatic authority escalation;
- user approval UX;
- cross-platform process sandboxing;
- network policy;
- malicious dependency containment;
- malicious model-weight containment;
- operating-system/kernel hardening.

## Smallest production intervention

The first production change should add authority without redesigning tool
handlers.

Target structure:

    ToolCall
       |
       v
    ToolExecutor
       |
       +--> schema validation
       |
       +--> AuthorityPolicy.authorize(...)
       |        |
       |        +--> deny -> ToolResult(ok=False, ...)
       |
       +--> handler(arguments)

This keeps authorization centralized and prevents individual tools from
implementing inconsistent policy logic.

The policy should receive normalized information sufficient to classify the
requested capability but should not depend on model reasoning.

## Required production tests

The production implementation must test at least:

1. repository read allowed when observation authority is granted;
2. repository read rejected when observation authority is absent;
3. repository mutation allowed when mutation authority is granted;
4. repository mutation rejected when mutation authority is absent;
5. approved check allowed when check authority is granted;
6. approved check rejected when check authority is absent;
7. denied calls do not invoke the handler;
8. authority denial returns a visible deterministic error;
9. repository content cannot mutate the authority grant;
10. tool arguments cannot expand the authority grant;
11. workspace confinement still rejects external paths independently of
    capability authority.

Existing production tests must continue to pass.

## Claims

Module 9 supports the following scoped claims:

1. Existing canonical workspace resolution handled all frozen path escape
   cases in 009A.

2. Strict tool schemas and a narrow command vocabulary prevented the frozen
   direct command-interface attacks, but did not contain the transitive
   authority of approved subprocesses.

3. The scoped Bubblewrap intervention prevented all four frozen transitive
   process effects while preserving the three tested approved checks.

4. Deterministic task authority prevented the observed prompt-injection
   proposal from becoming an execution or side effect without eliminating
   the compromised proposal itself.

5. In the five-task 009D diagnostic, capability-level authority produced the
   same observed coding behavior as unrestricted authority.

6. Exact-resource authority demonstrated both stronger containment and a
   legitimate-action rejection.

These claims do not establish that Hewn is generally secure.

## Architectural conclusion

Security should not depend on making the coding model perfectly obedient.

Hewn should instead make the model powerful inside an explicit authority
boundary.

The resulting separation is:

    reasoning        -> model
    protocol         -> deterministic parser
    argument shape   -> deterministic schema
    authority        -> deterministic policy
    path confinement -> deterministic workspace
    process isolation-> execution backend
    correctness      -> deterministic verification where available

This preserves the broader Hewn design principle:

> Use models where reasoning adds information. Use deterministic mechanisms
> where the answer is already mechanically available.