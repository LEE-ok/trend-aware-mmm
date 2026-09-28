"""Load and split the v0.2 weekly contract CSV (standard library only).

Required columns: wk_strt_dt, sales, mdsp_dm, mdsp_so, mdsp_vidtr,
mdsp_viddig, mdsp_sem. Extra columns are carried in ``extras`` when
requested, otherwise ignored.
"""
import csv
from datetime import date
from pathlib import Path

from .validation import DATE_COLUMN, SPEND_COLUMNS, TARGET_COLUMN, validate_csv

ROW_KEY = DATE_COLUMN


def load_weekly(path: str | Path, extra: tuple[str, ...] = ()) -> list[dict]:
    """Return sorted row dicts. Raises ValueError if the CSV is invalid."""
    errors = validate_csv(path)
    if errors:
        raise ValueError("; ".join(errors[:5]))
    rows = []
    with Path(path).open(encoding="utf-8-sig", newline="") as stream:
        for record in csv.DictReader(stream):
            rows.append(
                {
                    "date": date.fromisoformat(record[DATE_COLUMN]),
                    "sales": float(record[TARGET_COLUMN]),
                    "spends": {ch: float(record[ch]) for ch in SPEND_COLUMNS},
                    "extras": {col: record.get(col, "") for col in extra},
                }
            )
    rows.sort(key=lambda r: r["date"])
    return rows


def time_split(rows: list[dict], test_weeks: int = 26) -> tuple[list[dict], list[dict]]:
    """Split ordered rows into (train, test). Test is the last N weeks."""
    if test_weeks < 1:
        raise ValueError("test_weeks must be >= 1")
    if len(rows) <= test_weeks:
        raise ValueError(f"Need more than {test_weeks} rows, got {len(rows)}.")
    return rows[: len(rows) - test_weeks], rows[len(rows) - test_weeks :]


def _median(values: list[float]) -> float:
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[mid]
    return (ordered[mid - 1] + ordered[mid]) / 2


def summarize(rows: list[dict]) -> dict:
    """Descriptive stats used for the EDA note. No modeling here."""
    summary: dict = {
        "n_weeks": len(rows),
        "start": rows[0]["date"].isoformat(),
        "end": rows[-1]["date"].isoformat(),
        "channels": {},
        "sales": {},
    }
    sales = [r["sales"] for r in rows]
    summary["sales"] = {
        "median": _median(sales),
        "min": min(sales),
        "max": max(sales),
    }
    for ch in SPEND_COLUMNS:
        values = [r["spends"][ch] for r in rows]
        summary["channels"][ch] = {
            "median": _median(values),
            "min": min(values),
            "max": max(values),
            "zero_weeks": sum(1 for v in values if v == 0),
        }
    return summary


def pearson(xs: list[float], ys: list[float]) -> float:
    """Pearson correlation, stdlib only. Returns 0.0 on zero variance."""
    n = len(xs)
    mx = sum(xs) / n
    my = sum(ys) / n
    cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    vx = sum((x - mx) ** 2 for x in xs)
    vy = sum((y - my) ** 2 for y in ys)
    if vx == 0 or vy == 0:
        return 0.0
    return cov / (vx * vy) ** 0.5
