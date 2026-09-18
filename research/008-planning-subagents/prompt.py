from __future__ import annotations

SYSTEM_PROMPT = """You are planning a repository change.

Your entire response must be one valid JSON object.

The first character of your response must be {
The last character of your response must be }

Do not write ```json.
Do not write Markdown fences.
Do not write prose before or after the JSON.

Return exactly this shape:

{
  "files": [
    {
      "path": "src/example.py",
      "symbols": ["example_symbol"],
      "operations": ["change the required behavior"]
    }
  ],
  "verification": [
    "tests/test_example.py"
  ]
}

Rules:
- Do not edit code.
- Include every file that must change.
- Do not include files that do not need changes.
- Operations must describe required changes, not implementation prose.
- Include verification targets needed to check the requested behavior.
- Use only repository-relative paths.
"""


def build_prompt(
    *,
    task: str,
    files: dict[str, str],
    structure: str | None,
) -> str:
    sections = [
        "Task:",
        task,
        "",
        "Repository files:",
    ]

    for path in sorted(files):
        sections.extend(
            [
                f"--- {path} ---",
                files[path],
            ]
        )

    if structure is not None:
        sections.extend(
            [
                "",
                structure,
            ]
        )

    return "\n".join(sections)