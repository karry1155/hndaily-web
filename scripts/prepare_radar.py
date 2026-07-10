#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.editorial_filter import InputError
from scripts.radar_adapter import adapt_hndaily
from scripts.radar_contract import ContractError, SCHEMA_VERSION
from scripts.radar_model import build_model_input


def write_json_atomic(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def main(argv: list[str]) -> int:
    if len(argv) != 4:
        print(
            "Usage: prepare_radar.py RAW_JSON MODEL_INPUT_JSON PREFILTER_JSON",
            file=sys.stderr,
        )
        return 1
    raw_path = Path(argv[1])
    output_path = Path(argv[2])
    try:
        raw = json.loads(raw_path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise InputError("raw JSON must be an object")
        candidates, records = adapt_hndaily(raw)
        model_input = build_model_input(candidates)
        audit = {
            "schema_version": SCHEMA_VERSION,
            "date": raw.get("date"),
            "article_count": raw.get("article_count"),
            "records": records,
        }
        write_json_atomic(output_path, model_input)
        write_json_atomic(Path(argv[3]), audit)
    except (OSError, json.JSONDecodeError, InputError, ContractError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(str(output_path.resolve()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
