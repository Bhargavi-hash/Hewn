# 008A Run 001 Notes

## Status

Valid diagnostic run.

The experiment completed all 16 frozen calls:

- 8 source-only planning calls;
- 8 source-plus-structure planning calls.

No infrastructure failure was observed.

## Primary result

Strict planning protocol validity was 0/8 in both conditions.

Every observed response began with a Markdown JSON fence rather than the
required raw JSON object.

Because the frozen parser intentionally does not strip Markdown fences, all
16 responses were correctly classified as protocol failures.

As a result, the predeclared plan-quality metrics are undefined for run 001.

This run therefore does not answer whether deterministic repository structure
improves planning quality.

## Qualitative observation

The raw generations contain JSON-shaped planning content inside the Markdown
fences. Some responses identify relevant repository scope, while others
contain substantive planning errors.

These observations are diagnostic only because the responses failed the
predeclared protocol and were not scored.

## Interpretation

Run 001 demonstrates a protocol-compliance failure under the frozen strict
planner interface.

It does not demonstrate that the model cannot produce useful planning
content.

It also does not provide evidence for or against the structural-grounding
hypothesis because neither condition produced parser-valid plans.

## Follow-up

Preserve run 001 unchanged.

Introduce one explicit protocol intervention for run 002 while keeping fixed:

- the eight tasks;
- repository contents;
- ground-truth manifests;
- plan schema;
- scoring rules;
- model;
- temperature;
- context window;
- maximum output tokens;
- the source-only versus source-plus-structure treatment.

The intervention should address only Markdown-fence protocol compliance.