from __future__ import annotations

from typing import Any


HAINAN_RELEVANCE_THRESHOLD = 6
FINAL_SCORE_THRESHOLD = 65
MAX_SELECTED = 8
TOP_COUNT = 4


def _page_number(value: Any) -> int:
    try:
        return int(str(value))
    except ValueError:
        return 9999


def ranking_key(event: dict[str, Any]) -> tuple[Any, ...]:
    scores = event.get("semantic_scores", {})
    return (
        -float(event.get("final_score", 0)),
        -int(scores.get("information_density", 0)),
        -int(event.get("content_length", 0)),
        _page_number(event.get("page")),
        int(event.get("seq", 9999)),
        str(event.get("master_candidate_id", event.get("candidate_id", ""))),
    )


def select_events(
    events: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    decisions = [dict(event) for event in sorted(events, key=ranking_key)]
    eligible: list[dict[str, Any]] = []
    for event in decisions:
        relevance = event.get("semantic_scores", {}).get("hainan_relevance", 0)
        if relevance < HAINAN_RELEVANCE_THRESHOLD:
            event.update(selected=False, rank=None, unselected_reason="below_hainan_relevance")
        elif event.get("final_score", 0) < FINAL_SCORE_THRESHOLD:
            event.update(selected=False, rank=None, unselected_reason="below_final_score")
        else:
            eligible.append(event)

    selected = eligible[:MAX_SELECTED]
    selected_ids = {event["event_id"] for event in selected}
    for rank, event in enumerate(selected, 1):
        event.update(selected=True, rank=rank, unselected_reason=None)
    for event in eligible[MAX_SELECTED:]:
        event.update(selected=False, rank=None, unselected_reason="daily_limit")

    return [event for event in decisions if event.get("event_id") in selected_ids], decisions
