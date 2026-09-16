# ADR 0002: Detect Agent Stagnation

## Context

Baseline 003 reached the 20-turn limit after one failed verification.
Following completion rejection, the model repeatedly proposed final
responses without further environment interaction.

The turn limit bounded resource consumption but could not distinguish
productive work from repeated non-progressing turns.

## Decision

Hewn will distinguish the global turn budget from consecutive
non-progressing model turns.

For the initial implementation, a tool interaction counts as progress.
A rejected final response does not.

After three consecutive non-progressing turns, the agent terminates with
a distinct stagnation failure.

This intentionally detects only the failure mode observed in Module 1.
Repeated identical tool observations are not yet deduplicated.

## Consequences

Hewn can terminate obvious completion-rejection loops before exhausting
the full turn budget.

This improves failure detection and resource efficiency. It does not
improve the model's ability to solve the task.

A model can still avoid stagnation detection by repeatedly invoking tools
without acquiring useful new information.

## Future Work

If experiments demonstrate repeated identical tool observations or other
forms of mechanical tool-use loops, progress can be extended to account
for observation novelty.

Semantic relevance should not be part of this policy; repository
understanding and planning belong to later modules.