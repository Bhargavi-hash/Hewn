# Evaluated Systems

## Hewn

System:

    Hewn v0.1

Frozen tag:

    hewn-v0.1-eval-freeze

Model:

    Qwen2.5-Coder-0.5B-Instruct

Role:

    Frozen local-small-model baseline.

## Frontier systems

Frontier systems must be selected before their benchmark results are
observed.

For every selected system record:

- product/agent name,
- exact model when exposed,
- product/model version when exposed,
- evaluation date,
- execution environment,
- configuration,
- permission mode,
- context/reasoning setting when exposed,
- pricing basis,
- whether token/tool telemetry is exposed.

If an implementation detail is not exposed by the provider, record it as
unknown rather than inferring it.

## Fairness

The comparison does not require identical internal tools.

Each system receives:

- the same task statement,
- the same initial repository contents,
- no hidden evaluator implementation,
- no manual code edits during execution.

Each system may use its normal coding-agent capabilities.

The external oracle determines correctness.
