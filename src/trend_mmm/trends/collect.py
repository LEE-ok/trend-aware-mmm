"""Trend document intake MVP (file-based, stdlib only).

Week-3 full crawlers are deferred. This module implements the same
contract on manually collected CSVs so the pipeline runs end to end:
collect (read) -> clean -> aggregate_weekly -> MMM-side join.

Document CSV columns: source_url, published_at, collected_at, category, score.
- published_at / collected_at: YYYY-MM-DD.
- category: free text label from the week-3 labeling scheme.
- score: 0..1 labeled signal strength (manual until auto-labeling lands).
"""
import csv
from datetime import date, timedelta
from pathlib import Path

REQUIRED_DOC_COLUMNS = ("source_url", "published_at", "collected_at", "category", "score")


def collect_csv(path: str | Path) -> list[dict]:
    """Read a manually collected trend CSV. Raises ValueError on bad schema."""
    docs = []
    with Path(path).open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        fields = reader.fieldnames or []
        missing = set(REQUIRED_DOC_COLUMNS) - set(fields)
        if missing:
            raise ValueError(f"Missing columns: {', '.join(sorted(missing))}")
        for line, row in enumerate(reader, start=2):
            try:
                score = float(row.get("score") or "")
            except (ValueError, TypeError):
                raise ValueError(f"Line {line}: score must be a number.")
            if not 0.0 <= score <= 1.0:
                raise ValueError(f"Line {line}: score must be within [0, 1].")
            try:
                published = date.fromisoformat((row.get("published_at") or "").strip())
                collected = date.fromisoformat((row.get("collected_at") or "").strip())
            except ValueError:
                raise ValueError(f"Line {line}: dates must be YYYY-MM-DD.")
            docs.append(
                {
                    "source_url": (row.get("source_url") or "").strip(),
                    "published_at": published,
                    "collected_at": collected,
                    "category": (row.get("category") or "").strip(),
                    "score": score,
                }
            )
    if not docs:
        raise ValueError("No document rows.")
    return docs


def clean_docs(docs: list[dict]) -> list[dict]:
    """Drop rows with empty url/category and future publishes. Sort by date."""
    cleaned = [d for d in docs if d["source_url"] and d["category"]]
    cleaned.sort(key=lambda d: d["published_at"])
    return cleaned


def week_start_sunday(day: date) -> date:
    """Map a date to its Sunday-start week (matches data_GIT weekly grain)."""
    return day - timedelta(days=(day.weekday() + 1) % 7)


def aggregate_weekly(docs: list[dict]) -> dict[str, dict]:
    """Group document scores by Sunday-start week.

    Returns {wk_strt_dt: {"n_docs": int, "mean_score": float}}.
    """
    buckets: dict[date, list[float]] = {}
    for doc in docs:
        buckets.setdefault(week_start_sunday(doc["published_at"]), []).append(doc["score"])
    return {
        day.isoformat(): {"n_docs": len(scores), "mean_score": sum(scores) / len(scores)}
        for day, scores in sorted(buckets.items())
    }
