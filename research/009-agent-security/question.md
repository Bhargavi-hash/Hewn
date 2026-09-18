# Module 9: Agent Security

## Research question

Can deterministic authority boundaries prevent unsafe or out-of-scope
coding-agent actions while preserving legitimate repository operations,
even when repository content or model output attempts to cross those
boundaries?

## Motivation

Hewn treats the language model as a proposer rather than an authority.

A coding model may generate incorrect, malformed, overly broad, or unsafe
tool arguments. Repository files may also contain instructions that attempt
to influence the model into taking actions unrelated to the user's task.

Security therefore cannot depend on the model recognizing every unsafe
request.

The system surrounding the model must enforce what actions are actually
permitted.

## Primary hypothesis

A deterministic tool-policy layer can block actions that cross the
workspace or granted tool authority while preserving legitimate repository
operations with low false-rejection rates.

## Secondary hypotheses

1. Workspace confinement should be enforced at tool execution time rather
   than through prompting alone.

2. Canonical path validation must account for traversal, absolute paths,
   and symbolic links rather than relying only on string-prefix checks.

3. Shell execution requires a separate authority model from file access
   because a command executed inside the repository can still affect
   resources outside it.

4. Repository content must be treated as untrusted data. Instructions
   discovered inside source files, documentation, comments, tests, or
   generated artifacts must not automatically expand the agent's authority.

5. Deterministic policy should reject an unauthorized action even when the
   model explicitly argues that the action is necessary.

6. Security mechanisms must be evaluated for both attack blocking and
   legitimate-task interference.

## Competing hypotheses

1. Existing workspace checks may already prevent most relevant file-system
   escapes.

2. Strict deterministic policies may block legitimate coding workflows
   often enough that they reduce agent usefulness.

3. Prompt-level instructions may reduce unsafe proposals enough that a
   stronger runtime policy adds little practical value.

4. A coarse command allowlist may be safer but too restrictive for real
   repository work.

5. More sophisticated security mechanisms may add complexity without
   measurable protection on the tested threat model.

## Scope

Module 9 studies the authority boundary around Hewn's coding-agent tools.

Included:

- repository path confinement;
- path traversal;
- absolute-path access;
- symbolic-link escape;
- file read/write authority;
- destructive operations;
- shell-command authority;
- command composition and indirection;
- environment and secret exposure;
- repository prompt injection;
- tool-argument validation;
- false-positive cost on legitimate repository operations.

Excluded:

- operating-system container or VM sandboxing;
- kernel exploits;
- malicious model weights;
- network-service exploitation;
- dependency supply-chain security;
- production multi-user isolation;
- persistent repository memory security, which belongs primarily to
  Module 10;
- broad coding-agent benchmarking, which belongs to Module 11.

## Security principle

> The model proposes actions. Hewn decides whether those actions are
> authorized.

Neither model confidence nor repository-provided instructions can expand
the authority granted by the agent runtime.

## Experimental discipline

The adversarial fixture set and expected policy outcomes must be frozen
before production defenses are changed.

Every blocked action must have a mechanically defined reason.

Every defense must also be tested against legitimate operations.

Security claims will be limited to the explicit threat model and tested
operations. Passing these experiments must not be described as making Hewn
generally secure.