# Module 5 — Context Engineering

## Research question

How should Hewn select, budget, order, and represent retrieved repository
evidence so that a small coding model can reason effectively without
wasting context?

## Motivation

Module 3 established deterministic repository structure.

Module 4 established a retrieval architecture that combines deterministic
exact-symbol lookup with local semantic retrieval for conceptual queries.

Retrieval, however, only determines which evidence is relevant.

A coding model still receives some representation of that evidence in
its prompt. Giving the model every retrieved result may increase context
size, introduce competing concepts, and make the intended evidence harder
to use.

This is particularly important for Hewn because its target environment
includes small local models with limited reasoning and context resources.

## Primary hypothesis

For small local coding models, a compact context containing the
highest-value repository evidence will produce better or equal task
performance than larger contexts containing additional
relevant-but-lower-value evidence.

## Competing hypothesis

Additional repository context helps resolve relationships and ambiguity.
Aggressive context reduction may therefore remove information required
for correct reasoning.

## Experimental questions

1. How does evidence count affect context size and retrieval coverage?
2. How does a fixed character budget affect the evidence retained?
3. Which representation is most useful: structural metadata, source
   excerpts, or a mixture?
4. Does evidence ordering affect small-model behavior?
5. Can redundant evidence be removed without losing useful information?
6. Do retrieval improvements translate into actual model-task success?

## Initial constraints

- Keep the Module 4 retrieval policy fixed while testing context policy.
- Do not tune specifically for the nine navigation tasks.
- Separate retrieval from context construction.
- Keep context construction deterministic initially.
- Measure both evidence coverage and actual model behavior.
- Preserve failed experiments.
- Do not introduce persistent repository memory yet.
- Do not claim generalization from Hewn self-navigation alone.

## Module boundary

Module 4 answers:

> Which repository evidence should be retrieved?

Module 5 answers:

> Which retrieved evidence should the model actually see, and in what
> form?

Persistent repository knowledge belongs to Module 10.
Model training belongs to Modules 14 and 15.
General benchmark construction belongs to Module 11.