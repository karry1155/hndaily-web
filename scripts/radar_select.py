from typing import Any

HAINAN_RELEVANCE_THRESHOLD = 6
FINAL_SCORE_THRESHOLD = 65
FOCUS_DAYS = 3
FOCUS_LIMIT = 4
FOCUS_DAY_PENALTY = 3


def _rank_key(item: dict[str, Any]) -> tuple[Any, ...]:
    return (
        -float(item["final_score"]),
        -int(item["semantic_scores"]["information_density"]),
        str(item["item_id"]),
    )


def select_items(
    items: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    decisions = [dict(item) for item in sorted(items, key=_rank_key)]
    selected = []
    for item in decisions:
        relevance = item["semantic_scores"]["hainan_relevance"]
        if relevance < HAINAN_RELEVANCE_THRESHOLD:
            item.update(
                selected=False,
                daily_rank=None,
                unselected_reason="below_hainan_relevance",
            )
        elif item["final_score"] < FINAL_SCORE_THRESHOLD:
            item.update(
                selected=False,
                daily_rank=None,
                unselected_reason="below_final_score",
            )
        else:
            item.update(
                selected=True,
                daily_rank=len(selected) + 1,
                unselected_reason=None,
            )
            selected.append(item)
    return selected, decisions


def select_focus(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    dates = sorted(
        {item["published_date"] for item in items}, reverse=True
    )[:FOCUS_DAYS]
    date_index = {value: index for index, value in enumerate(dates)}
    candidates = []
    for item in items:
        if item["published_date"] not in date_index:
            continue
        copy = dict(item)
        copy["focus_score"] = float(item["final_score"]) - (
            FOCUS_DAY_PENALTY * date_index[item["published_date"]]
        )
        candidates.append(copy)
    candidates.sort(
        key=lambda item: (
            -item["focus_score"],
            -item["final_score"],
            -int(item["published_date"].replace("-", "")),
            item["item_id"],
        )
    )
    focus = candidates[:FOCUS_LIMIT]
    for rank, item in enumerate(focus, 1):
        item["focus_rank"] = rank
    return focus
