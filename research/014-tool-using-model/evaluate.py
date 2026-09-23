from __future__ import annotations

import argparse
import json
import time
from pathlib import Path


def norm(x):
    if isinstance(x, dict):
        return {k: norm(v) for k, v in sorted(x.items())}
    if isinstance(x, list):
        return [norm(v) for v in x]
    return x


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--model",
        default="Qwen/Qwen2.5-Coder-0.5B-Instruct",
    )
    ap.add_argument("--adapter", type=Path)
    ap.add_argument("--eval", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()

    try:
        import torch
        from peft import PeftModel
        from transformers import AutoModelForCausalLM, AutoTokenizer
    except ImportError as e:
        raise SystemExit(
            "Install: pip install torch transformers peft accelerate"
        ) from e

    device = torch.device(
        "cuda" if torch.cuda.is_available() else "cpu"
    )
    dtype = (
        torch.float16
        if torch.cuda.is_available()
        else torch.float32
    )

    print(f"device: {device}")
    if torch.cuda.is_available():
        print(f"gpu: {torch.cuda.get_device_name(0)}")
    print(f"dtype: {dtype}")

    tok = AutoTokenizer.from_pretrained(a.model)

    model = AutoModelForCausalLM.from_pretrained(
        a.model,
        dtype=dtype,
        low_cpu_mem_usage=True,
    )

    if a.adapter:
        model = PeftModel.from_pretrained(model, a.adapter)

    model = model.to(device)
    model.eval()

    rows = [
        json.loads(x)
        for x in a.eval.read_text().splitlines()
        if x.strip()
    ]

    rec = []
    start = time.perf_counter()

    for r in rows:
        msgs = [
            {"role": "system", "content": r["system"]},
            {"role": "user", "content": r["prompt"]},
        ]

        prompt = tok.apply_chat_template(
            msgs,
            tokenize=False,
            add_generation_prompt=True,
        )

        inp = tok(
            prompt,
            return_tensors="pt",
        ).to(device)

        with torch.no_grad():
            out = model.generate(
                **inp,
                max_new_tokens=160,
                do_sample=False,
                pad_token_id=tok.eos_token_id,
            )

        raw = tok.decode(
            out[0, inp["input_ids"].shape[1]:],
            skip_special_tokens=True,
        ).strip()

        try:
            parsed = json.loads(raw)
            valid = isinstance(parsed, dict)
        except json.JSONDecodeError:
            parsed = {}
            valid = False

        exp = json.loads(r["target"])

        rec.append(
            {
                "family": r["family"],
                "raw": raw,
                "valid_json": valid,
                "action_correct": (
                    valid
                    and parsed.get("type") == exp.get("type")
                    and parsed.get("name") == exp.get("name")
                ),
                "exact_action": (
                    valid and norm(parsed) == norm(exp)
                ),
            }
        )

    n = len(rec)

    result = {
        "model": a.model,
        "adapter": str(a.adapter) if a.adapter else None,
        "runs": n,
        "valid_json_rate": (
            sum(x["valid_json"] for x in rec) / n
        ),
        "action_correct_rate": (
            sum(x["action_correct"] for x in rec) / n
        ),
        "exact_action_rate": (
            sum(x["exact_action"] for x in rec) / n
        ),
        "wall_seconds": time.perf_counter() - start,
        "records": rec,
    }

    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(
        json.dumps(result, indent=2) + "\n"
    )

    print(
        json.dumps(
            {
                k: v
                for k, v in result.items()
                if k != "records"
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
