#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.prepare_radar import write_json_atomic
from scripts.radar_topics import (
    automatic_topic_resolution,
    build_topic_resolution_input,
    load_topic_catalog,
)


def main(argv: list[str]) -> int:
    if len(argv) != 5:
        print(
            "Usage: prepare_topic_resolution.py MODEL_OUTPUT CONTENT_ROOT RESOLUTION_INPUT RESOLUTION_OUTPUT",
            file=sys.stderr,
        )
        return 1
    try:
        model_output = json.loads(Path(argv[1]).read_text(encoding="utf-8"))
        catalog = load_topic_catalog(Path(argv[2]))
        resolution_input = build_topic_resolution_input(model_output, catalog)
        write_json_atomic(Path(argv[3]), resolution_input)
        output_path = Path(argv[4])
        automatic = automatic_topic_resolution(resolution_input)
        if automatic is not None:
            write_json_atomic(output_path, automatic)
        return 0 if output_path.is_file() else 2
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
