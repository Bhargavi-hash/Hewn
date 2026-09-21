from __future__ import annotations

from pathlib import Path


OUTPUT_DIR = Path(
    "research/012-running-models-locally/prompts/012e-consumed-context"
)

HEADER = """\
You are reviewing a synthetic Python repository.

Read the repository excerpts below and identify potential correctness
problems. Give a concise explanation of the most important issue.

Repository excerpts:

"""

BLOCK_TEMPLATE = """\
# file: synthetic/module_{index:04d}.py

def transform_{index:04d}(values):
    total = 0
    for value in values:
        if value >= {threshold}:
            total += value
    return total


def normalize_{index:04d}(values):
    if not values:
        return []
    maximum = max(values)
    return [value / maximum for value in values]


"""


def build_corpus(blocks: int = 500) -> str:
    parts = [HEADER]

    for index in range(blocks):
        parts.append(
            BLOCK_TEMPLATE.format(
                index=index,
                threshold=(index % 17) + 1,
            )
        )

    return "".join(parts)


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    corpus = build_corpus()
    output_path = OUTPUT_DIR / "corpus.txt"

    output_path.write_text(
        corpus,
        encoding="utf-8",
    )

    print(f"wrote: {output_path}")
    print(f"characters: {len(corpus)}")


if __name__ == "__main__":
    main()