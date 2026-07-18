#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.radar_indexes import build_hnhot_indexes
from scripts.radar_store import commit_publication, load_issue_items, load_issues


def migrate(content_root: Path) -> tuple[int, int]:
    issues = load_issues(content_root)
    articles = load_issue_items(content_root)
    indexes = build_hnhot_indexes(issues, articles)
    by_date = {
        issue["date"]: [
            article for article in articles if article["published_date"] == issue["date"]
        ]
        for issue in issues
    }
    for issue in issues:
        commit_publication(content_root, issue, by_date[issue["date"]], indexes)
    return len(issues), len(articles)


def main(argv):
    root = Path(argv[1]) if len(argv) > 1 else Path(__file__).resolve().parents[1] / "content"
    try:
        issues, articles = migrate(root)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(f"Migrated {issues} issues and {articles} articles to HNHOT schema v7")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
