# Research 001 — The Minimal Coding Agent

## Question

What is the minimum tool and control-loop architecture required for a
language model to autonomously solve simple repository-level coding tasks?

## Motivation

A language model alone can generate code but cannot inspect or modify a
repository, execute commands, or observe the consequences of its changes.

A coding agent adds an external control loop that allows the model to
interact with a software-development environment through tools.

Before adding repository indexing, semantic retrieval, persistent memory,
planning, subagents, or specialized models, Hewn needs a minimal measurable
baseline.

## Baseline

TinyHewn will initially expose only four capabilities:

1. List files.
2. Read files.
3. Apply controlled file modifications.
4. Execute approved development commands.

The model may repeatedly select tools until it either completes the task,
fails, or reaches an iteration limit.

## Hypothesis

A language model connected to a minimal iterative tool loop can solve simple
repository-level debugging tasks without repository indexing, semantic
retrieval, persistent memory, or explicit planning.

However, we expect the baseline to become inefficient or unreliable as
repository size and task ambiguity increase.

## What We Will Measure

- task success
- iterations
- model calls
- tool calls
- files read
- files modified
- commands executed
- wall-clock time
- model input/output usage when available
- test outcome
- failure category

## Why This Matters

This experiment establishes the baseline against which future Hewn
capabilities will be evaluated.

Every later optimization should demonstrate whether it improves the agent
relative to this minimal architecture.