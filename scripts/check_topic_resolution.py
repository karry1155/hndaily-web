#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.radar_topics import load_topic_catalog, validate_topic_resolution_output


def main(argv: list[str]) -> int:
    if len(argv) != 4:
        print(
            "Usage: check_topic_resolution.py RESOLUTION_INPUT RESOLUTION_OUTPUT CONTENT_ROOT",
            file=sys.stderr,
        )
        return 1
    try:
        resolution_input = json.loads(Path(argv[1]).read_text(encoding="utf-8"))
        resolution_output = json.loads(Path(argv[2]).read_text(encoding="utf-8"))
        catalog = load_topic_catalog(Path(argv[3]))
        validate_topic_resolution_output(resolution_input, resolution_output, catalog)
        return 0
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"TOPIC_RESOLUTION_INVALID={exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
