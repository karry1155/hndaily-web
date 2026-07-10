from __future__ import annotations

import json
import shutil
from pathlib import Path

from scripts.radar_contract import validate_stored_item


def _write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def load_items(content_root: Path):
    result = []
    for path in sorted((content_root / "items").glob("*/*.json")):
        value = json.loads(path.read_text(encoding="utf-8"))
        validate_stored_item(value)
        result.append(value)
    return result


def commit_generation(
    content_root: Path,
    items,
    indexes,
    affected_dates,
    *,
    fail_after_items=False,
):
    content_root = Path(content_root)
    for item in items:
        validate_stored_item(item)
    ids = [item["item_id"] for item in items]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate item_id in library")
    staging = content_root / ".radar-store-staging"
    if staging.exists():
        shutil.rmtree(staging)
    for published_date in affected_dates:
        date_dir = staging / "items" / published_date
        date_dir.mkdir(parents=True, exist_ok=True)
        for item in items:
            if item["published_date"] == published_date:
                _write_json(date_dir / f"{item['item_id']}.json", item)
    for relative, payload in indexes.items():
        _write_json(staging / "indexes" / relative, payload)
    (staging / "indexes").mkdir(parents=True, exist_ok=True)

    swaps = []
    try:
        for published_date in sorted(affected_dates):
            target = content_root / "items" / published_date
            backup = content_root / "items" / f".{published_date}.radar-backup"
            target.parent.mkdir(parents=True, exist_ok=True)
            if backup.exists():
                shutil.rmtree(backup)
            had_target = target.exists()
            if had_target:
                target.replace(backup)
            (staging / "items" / published_date).replace(target)
            swaps.append((target, backup, had_target))
        if fail_after_items:
            raise RuntimeError("injected failure after item swaps")
        target = content_root / "indexes"
        backup = content_root / ".indexes.radar-backup"
        if backup.exists():
            shutil.rmtree(backup)
        had_target = target.exists()
        if had_target:
            target.replace(backup)
        (staging / "indexes").replace(target)
        swaps.append((target, backup, had_target))
    except Exception:
        for target, backup, had_target in reversed(swaps):
            if target.exists():
                shutil.rmtree(target)
            if had_target and backup.exists():
                backup.replace(target)
        raise
    else:
        for _, backup, _ in swaps:
            if backup.exists():
                shutil.rmtree(backup)
    finally:
        if staging.exists():
            shutil.rmtree(staging)
