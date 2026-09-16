# Experiment 001 — Structural Repository Map

## Question

Does exposing deterministic repository structure improve a small model's
ability to answer repository navigation questions, especially conceptual
questions whose relevant symbol name is not given directly?

## Baseline

Module 2 semantic-symbol configuration.

Available capabilities include the existing primitive tools plus
`find_symbol`.

## Treatment

Same configuration, with one additional tool:

`repository_map`

The tool exposes:

- repository-relative source files
- defined symbols
- qualified symbol names
- internal file dependencies

It does not expose source bodies.

## Controlled Variables

- model
- model weights and quantization
- inference server
- temperature
- task set
- task order
- evaluator
- completion policy
- turn limit
- system prompt, except automatically exposed tool definitions

## Primary Metrics

- tasks passed
- conceptual tasks passed
- model calls
- tool calls
- tool-selection failures
- protocol failures

## Hypothesis

Structural repository knowledge will primarily help conceptual navigation
tasks where the relevant symbol name is not present in the user request.

## Interpretation

A result on this nine-task Hewn benchmark is evidence about this benchmark
configuration only. It is not evidence of general coding-agent superiority.