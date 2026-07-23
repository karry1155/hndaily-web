#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.radar_model import ModelOutputError, validate_model_output


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print("Usage: check_model_output.py MODEL_INPUT_JSON MODEL_OUTPUT_JSON", file=sys.stderr)
        return 1
    try:
        model_input = json.loads(Path(argv[1]).read_text(encoding="utf-8"))
        model_output = json.loads(Path(argv[2]).read_text(encoding="utf-8"))
        candidates = [
            {
                "candidate_id": row["candidate_id"],
                "title": row["title"],
                "content": row["content"],
            }
            for row in model_input["items"]
        ]
        validate_model_output(model_input, model_output, candidates)
    except (OSError, json.JSONDecodeError, KeyError, TypeError, ModelOutputError) as exc:
        print(f"MODEL_OUTPUT_INVALID={exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
