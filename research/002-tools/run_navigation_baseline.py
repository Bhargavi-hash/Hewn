from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from hewn.agent import Agent, AgentLimitError, AgentStagnationError
from hewn.builtin_tools import make_builtin_tool_registry
from hewn.completion import CompletionRequirement
from hewn.llama_cpp import LlamaCppModel
from hewn.model_protocol import ModelProtocolError
from hewn.tools import ToolExecutor
from hewn.workspace import Workspace

REPO_ROOT = Path(__file__).resolve().parents[2]
TASKS_PATH = Path(__file__).with_name("tasks.json")
RESULTS_DIR = Path(__file__).with_name("results")


def load_tasks() -> list[dict[str, Any]]:
    data = json.loads(TASKS_PATH.read_text(encoding="utf-8"))

    if not isinstance(data, list):
        raise TypeError("tasks.json must contain a JSON array")

    return data


def evaluate_answer(
    *,
    answer: str,
    expected_file: str,
    expected_symbol: str,
) -> bool:
    return (
        expected_file in answer
        and expected_symbol in answer
    )

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the Hewn repository-navigation benchmark."
    )
    parser.add_argument(
        "--output",
        default="primitive-run-001.json",
        help="Result filename written inside research/002-tools/results/.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    tasks = load_tasks()
    RESULTS_DIR.mkdir(exist_ok=True)

    workspace = Workspace(REPO_ROOT)

    # Use the same primitive tool vocabulary established in Module 1.
    registry = make_builtin_tool_registry(workspace)
    executor = ToolExecutor(registry)

    results: list[dict[str, Any]] = []

    for task in tasks:
        print(f"Running {task['id']}: {task['task']}")

        model = LlamaCppModel()

        agent = Agent(
            model=model,
            registry=registry,
            executor=executor,
        )

        try:
            run = agent.run(
                task["task"],
                completion_requirement=CompletionRequirement.NONE,
            )

            success = evaluate_answer(
                answer=run.text,
                expected_file=task["expected_file"],
                expected_symbol=task["expected_symbol"],
            )

            results.append(
                {
                    "id": task["id"],
                    "category": task["category"],
                    "task": task["task"],
                    "expected_file": task["expected_file"],
                    "expected_symbol": task["expected_symbol"],
                    "success": success,
                    "status": "completed",
                    "answer": run.text,
                    "metrics": asdict(run.metrics),
                }
            )

            print(
                f"  {'PASS' if success else 'FAIL'} "
                f"({run.metrics.model_calls} model calls, "
                f"{run.metrics.tool_calls} tool calls)"
            )

        except (AgentLimitError, AgentStagnationError) as error:
            results.append(
                {
                    "id": task["id"],
                    "category": task["category"],
                    "task": task["task"],
                    "expected_file": task["expected_file"],
                    "expected_symbol": task["expected_symbol"],
                    "success": False,
                    "status": type(error).__name__,
                    "answer": None,
                    "metrics": asdict(error.metrics),
                }
            )

            print(f"  FAIL ({type(error).__name__})")

        except ModelProtocolError as error:
            results.append(
                {
                    "id": task["id"],
                    "category": task["category"],
                    "task": task["task"],
                    "expected_file": task["expected_file"],
                    "expected_symbol": task["expected_symbol"],
                    "success": False,
                    "status": "ModelProtocolError",
                    "answer": None,
                    "raw_model_response": error.raw_response,
                    "metrics": None,
                }
            )

            print("  FAIL (ModelProtocolError)")

    output_path = RESULTS_DIR / args.output
    output_path.write_text(
        json.dumps(results, indent=2),
        encoding="utf-8",
    )

    passed = sum(result["success"] for result in results)

    print()
    print(f"Completed: {passed}/{len(results)} tasks passed")
    print(f"Results: {output_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())