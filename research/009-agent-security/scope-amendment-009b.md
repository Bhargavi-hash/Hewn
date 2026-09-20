# Module 9 Scope Amendment: 009B-H

## Status

Post-baseline, evidence-driven scope amendment.

This amendment does not modify the original Module 9 research question,
threat model, or experiment definitions retroactively. It records why one
narrow process-isolation intervention was added after observing the frozen
009B baseline.

## Original boundary

Module 9 originally excluded operating-system sandbox engineering, kernel
hardening, and production-grade process isolation.

The intended focus was deterministic authority enforcement at Hewn's tool
boundary.

## Evidence that motivated the amendment

009A showed that Hewn's existing workspace path boundary correctly rejected
all seven frozen unauthorized path cases while accepting all four authorized
path cases.

009B then separated model-facing command selection from the authority of the
process launched by an approved command.

In command-authority run-002:

- all 4/4 invalid model-facing command requests were rejected;
- all 3/3 legitimate approved checks were allowed and successful;
- all 4/4 transitive-authority fixtures produced the external effect.

The approved pytest process could therefore:

1. read a disposable file outside the workspace;
2. write a disposable file outside the workspace;
3. read a synthetic inherited environment value;
4. launch a child process that read a disposable file outside the workspace.

This established that command allowlisting and strict tool schemas constrain
what command the model can request, but do not constrain the transitive
authority exercised by repository-controlled code executed by that command.

Additional command-name validation would not address that observed boundary.

## Narrow amendment

Module 9 is therefore amended to permit one Linux process-isolation
feasibility intervention around approved development checks.

009B-H evaluates an experimental Bubblewrap boundary that provides:

- an explicitly mounted read-only system runtime;
- explicitly mounted read-only Python and tool runtimes;
- a writable repository workspace;
- a private temporary directory;
- an explicitly constructed environment;
- namespace isolation, including network isolation;
- no intentional mount of the evaluator's disposable external directory.

The intervention is evaluated against the same frozen command-authority
corpus used to expose the baseline boundary.

## Result

In 009B-H run-001:

- all 4/4 model-facing interface rejection cases remained rejected;
- all 3/3 legitimate approved checks remained successful;
- all 4/4 frozen transitive external effects were prevented.

Within this diagnostic, the process-isolation intervention therefore removed
the observed transitive-authority effects without reducing utility on the
three approved development checks.

## Remaining exclusions

This amendment does not expand Module 9 into general sandbox engineering.

The following remain outside the scope of the current result:

- general kernel hardening;
- proof of sandbox correctness;
- Bubblewrap vulnerability analysis;
- cross-platform sandbox implementation;
- Windows or macOS isolation;
- malicious dependencies or model weights;
- comprehensive filesystem authority analysis;
- production multi-user isolation;
- production sandbox lifecycle management;
- general network-policy evaluation;
- container or virtual-machine isolation comparisons;
- claims of complete coding-agent security.

## Interpretation boundary

009B-H is evidence that process isolation can address the specific transitive
authority failures observed in the frozen 009B corpus on the current Linux
environment.

It is not evidence that Bubblewrap is universally sufficient, that the
sandbox is production-ready, or that Hewn is generally secure.

The architectural result is narrower:

> A strict model-facing command interface limits requested authority, but
> repository-controlled code executed by an approved command requires a
> separate execution boundary if its process authority must also be
> constrained.