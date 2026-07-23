from __future__ import annotations

import json
import shutil
from pathlib import Path

from scripts.radar_issue import validate_public_issue, validate_public_issue_item


def _write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def load_issues(content_root: Path):
    result = []
    for path in sorted((content_root / "issues").glob("*.json")):
        value = json.loads(path.read_text(encoding="utf-8"))
        validate_public_issue(value)
        result.append(value)
    return result


def load_issue_items(content_root: Path):
    result = []
    for path in sorted((content_root / "issue-items").glob("*/*.json")):
        value = json.loads(path.read_text(encoding="utf-8"))
        validate_public_issue_item(value)
        result.append(value)
    return result


def commit_publication(content_root: Path, issue, issue_items, indexes) -> None:
    """Atomically replace one newspaper date and all derived HNHOT indexes."""
    content_root = Path(content_root)
    validate_public_issue(issue)
    for item in issue_items:
        validate_public_issue_item(item)
    if len({item["item_id"] for item in issue_items}) != len(issue_items):
        raise ValueError("duplicate item_id in publication")
    published_date = issue["date"]
    staging = content_root / ".hnhot-store-staging"
    if staging.exists():
        shutil.rmtree(staging)
    _write_json(staging / "issues" / f"{published_date}.json", issue)
    for item in issue_items:
        _write_json(
            staging
            / "issue-items"
            / published_date
            / f'{item["item_id"]}.json',
            item,
        )
    for relative, payload in indexes.items():
        _write_json(staging / "indexes" / relative, payload)
    swaps = []
    targets = [
        (
            staging / "issues" / f"{published_date}.json",
            content_root / "issues" / f"{published_date}.json",
        ),
        (
            staging / "issue-items" / published_date,
            content_root / "issue-items" / published_date,
        ),
        (staging / "indexes", content_root / "indexes"),
    ]
    try:
        for source, target in targets:
            target.parent.mkdir(parents=True, exist_ok=True)
            backup = target.with_name(f".{target.name}.hnhot-backup")
            if backup.exists():
                shutil.rmtree(backup) if backup.is_dir() else backup.unlink()
            had_target = target.exists()
            if had_target:
                target.replace(backup)
            source.replace(target)
            swaps.append((target, backup, had_target))
    except Exception:
        for target, backup, had_target in reversed(swaps):
            if target.exists():
                shutil.rmtree(target) if target.is_dir() else target.unlink()
            if had_target and backup.exists():
                backup.replace(target)
        raise
    else:
        for _, backup, _ in swaps:
            if backup.exists():
                shutil.rmtree(backup) if backup.is_dir() else backup.unlink()
    finally:
        if staging.exists():
            shutil.rmtree(staging)
