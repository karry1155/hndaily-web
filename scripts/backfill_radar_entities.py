#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

from scripts.radar_contract import SCHEMA_VERSION
from scripts.radar_indexes import build_indexes, build_issue_date_index, build_search_indexes
from scripts.radar_store import commit_generation

EMPTY = {"actors": [], "locations": [], "action": "", "action_evidence": ""}
KNOWN = {
    "hndaily-19691669": {
        "actors": [{"name":"冯飞","type":"person","role":"省委书记","evidence":"省委书记冯飞在三沙市调研"}],
        "locations": [{"location_id":"hainan-sansha","name":"三沙市","code":"460300","level":"prefecture","evidence":"在三沙市调研"}],
        "action":"调研学习教育及经济社会发展情况","action_evidence":"调研树立和践行正确政绩观学习教育及经济社会发展情况"
    },
    "hndaily-19691670": {
        "actors": [{"name":"刘小明","type":"person","role":"省长","evidence":"省长刘小明来到白沙黎族自治县"}],
        "locations": [{"location_id":"hainan-baisha","name":"白沙黎族自治县","code":"469025","level":"county","evidence":"来到白沙黎族自治县"}],
        "action":"调研乡村振兴并参加联合主题党日活动","action_evidence":"参加所在的省政府办公厅秘书一处党支部与南训村党委联合主题党日活动"
    },
    "hndaily-19691671": {
        "actors": [{"name":"省政协","type":"government","role":None,"evidence":"省政协八届常委会第二十四次会议"}],
        "locations": [{"location_id":"hainan-haikou","name":"海口市","code":"460100","level":"prefecture","evidence":"在海口召开"}],
        "action":"召开八届常委会第二十四次会议","action_evidence":"省政协八届常委会第二十四次会议在海口召开"
    },
}


def backfill_entities(content_root: Path):
    items = []
    for path in sorted((content_root / "items").glob("*/*.json")):
        item = json.loads(path.read_text(encoding="utf-8"))
        item["schema_version"] = SCHEMA_VERSION
        item["entities"] = KNOWN.get(item["item_id"], EMPTY)
        items.append(item)
    issues = []
    for path in sorted((content_root / "issues").glob("*.json")):
        value = json.loads(path.read_text(encoding="utf-8")); value["schema_version"] = SCHEMA_VERSION; issues.append(value)
    issue_items = []
    for path in sorted((content_root / "issue-items").glob("*/*.json")):
        value = json.loads(path.read_text(encoding="utf-8")); value["schema_version"] = SCHEMA_VERSION; issue_items.append(value)
    as_of = max((item["published_date"] for item in items), default="2026-07-12")
    indexes = build_indexes(items, as_of)
    indexes.update(build_search_indexes(items, issue_items))
    indexes["issues.json"] = build_issue_date_index(issues)
    commit_generation(
        content_root, items, indexes,
        {item["published_date"] for item in items},
        issues=issues, issue_items=issue_items,
    )
    return {"item_count": len(items), "tagged_count": sum(bool(item["entities"]["actors"] or item["entities"]["locations"]) for item in items)}


def main(argv):
    root = Path(argv[1]) if len(argv) == 2 else Path("content")
    print(json.dumps(backfill_entities(root), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
