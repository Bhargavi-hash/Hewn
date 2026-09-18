from __future__ import annotations

SYSTEM_PROMPT = """You are planning a repository change.

Return exactly one JSON object and nothing else.

The JSON schema is:

{
  "files": [
    {
      "path": "repository-relative path",
      "symbols": ["symbol names relevant to the change"],
      "operations": ["concrete changes required in this file"]
    }
  ],
  "verification": [
    "repository-relative test or verification paths"
  ]
}

Rules:
- Do not edit code.
- Include every file that must change.
- Do not include files that do not need changes.
- Operations must describe required changes, not implementation prose.
- Include verification targets needed to check the requested behavior.
- Use only repository-relative paths.
- Do not use Markdown.
- Do not include commentary outside the JSON object.
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