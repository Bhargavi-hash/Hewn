# Module 6 — How Coding Agents Edit Code

## Research question

What editing abstraction lets a small coding model modify repository code reliably while minimizing unintended changes and recovery work?

## Motivation

Modules 3–5 improved repository understanding, retrieval, and context construction. The final Module 5 integration experiment showed that correct repository evidence can reach the model without guaranteeing successful downstream behavior.

Module 6 studies a different boundary: once the relevant code is available, how should a coding agent express and apply modifications?

Hewn currently exposes `replace_text`, an exact-once string replacement tool. The model supplies a file path, an existing text fragment, and replacement text. Hewn rejects the operation if the existing fragment occurs zero times or more than once.

This creates a targeting tradeoff. Small target strings are easier for a model to reproduce but may be ambiguous. Larger target strings can disambiguate the location but require more exact reproduction of the current source.

## Primary hypothesis

Exact-once text replacement will be reliable for small localized edits when the target source is already available to the model, but failures will increase when changes require disambiguating repeated text, inserting code, modifying multiple locations, or coordinating multiple files.

## Competing hypothesis

The simplicity and explicit failure behavior of exact-once replacement may be sufficient for a small model across a wider range of editing tasks than expected. More structured editing mechanisms may add protocol complexity without improving end-to-end reliability.

## Experimental principle

Do not add a new editing primitive until the existing primitive's failure modes have been measured.

A rejected ambiguous edit is preferable to a silently misapplied edit.