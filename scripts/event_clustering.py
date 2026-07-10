from __future__ import annotations

import re
from typing import Any


TITLE_NGRAM_SIZE = 2
LEAD_NGRAM_SIZE = 3
LEAD_CHARACTERS = 500
TITLE_SIMILARITY_THRESHOLD = 0.78
LEAD_SIMILARITY_THRESHOLD = 0.72
TITLE_CONTAINMENT_THRESHOLD = 0.15
LEAD_CONTAINMENT_THRESHOLD = 0.45
_NON_WORD_RE = re.compile(r"[\W_]+", re.UNICODE)


def normalize_text(value: Any) -> str:
    return _NON_WORD_RE.sub("", str(value or "")).lower()


def ngrams(value: str, size: int) -> set[str]:
    if not value:
        return set()
    if len(value) <= size:
        return {value}
    return {value[index:index + size] for index in range(len(value) - size + 1)}


def jaccard(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def containment(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    return len(left & right) / min(len(left), len(right))


def _is_duplicate(left: dict[str, Any], right: dict[str, Any]) -> bool:
    left_title = normalize_text(left.get("original_title"))
    right_title = normalize_text(right.get("original_title"))
    if left_title and left_title == right_title:
        return True
    left_title_ngrams = ngrams(left_title, TITLE_NGRAM_SIZE)
    right_title_ngrams = ngrams(right_title, TITLE_NGRAM_SIZE)
    title_similarity = jaccard(left_title_ngrams, right_title_ngrams)
    if title_similarity >= TITLE_SIMILARITY_THRESHOLD:
        return True
    left_lead = normalize_text(left.get("content"))[:LEAD_CHARACTERS]
    right_lead = normalize_text(right.get("content"))[:LEAD_CHARACTERS]
    left_lead_ngrams = ngrams(left_lead, LEAD_NGRAM_SIZE)
    right_lead_ngrams = ngrams(right_lead, LEAD_NGRAM_SIZE)
    lead_similarity = jaccard(left_lead_ngrams, right_lead_ngrams)
    if lead_similarity >= LEAD_SIMILARITY_THRESHOLD:
        return True
    return (
        containment(left_title_ngrams, right_title_ngrams) >= TITLE_CONTAINMENT_THRESHOLD
        and containment(left_lead_ngrams, right_lead_ngrams) >= LEAD_CONTAINMENT_THRESHOLD
    )


def _page_number(value: Any) -> int:
    try:
        return int(str(value))
    except ValueError:
        return 9999


def _master_key(candidate: dict[str, Any]) -> tuple[Any, ...]:
    scores = candidate.get("semantic_scores", {})
    return (
        -int(scores.get("information_density", 0)),
        -int(candidate.get("content_length", 0)),
        -float(candidate.get("final_score", 0)),
        _page_number(candidate.get("page")),
        int(candidate.get("seq", 9999)),
        str(candidate.get("candidate_id", "")),
    )


def _choose_master(members: list[dict[str, Any]]) -> dict[str, Any]:
    return min(members, key=_master_key)


def cluster_candidates(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ordered = sorted(candidates, key=lambda item: str(item.get("candidate_id", "")))
    clusters: list[list[dict[str, Any]]] = []
    for candidate in ordered:
        for members in clusters:
            if _is_duplicate(candidate, _choose_master(members)):
                members.append(candidate)
                break
        else:
            clusters.append([candidate])

    events: list[dict[str, Any]] = []
    for index, members in enumerate(clusters, 1):
        master = _choose_master(members)
        event = dict(master)
        event.update(
            {
                "event_id": f"E{index:03d}",
                "master_candidate_id": master["candidate_id"],
                "member_candidate_ids": [item["candidate_id"] for item in members],
                "sources": [
                    {
                        "headline": item["original_title"],
                        "page": item["page"],
                        "url": item["url"],
                    }
                    for item in members
                ],
            }
        )
        events.append(event)
    return events
