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


# --- Controls / holidays / seasonality (docs/priors.md v1.0 decisions) ---

CONTROL_COLUMNS = ("me_gas_dpg", "me_ics_all", "st_ct")
YEAR_END_HOLIDAYS = (
    "hldy_Christmas Eve",
    "hldy_Christmas Day",
    "hldy_Day after Christmas",
    "hldy_NYE",
    "hldy_New Year's Day",
)


def discover_columns(path: str | Path) -> dict:
    """Group extra CSV columns by prefix. Missing groups come back empty."""
    import csv as _csv

    with Path(path).open(encoding="utf-8-sig", newline="") as stream:
        fields = _csv.DictReader(stream).fieldnames or []
    controls = [c for c in CONTROL_COLUMNS if c in fields]
    holidays = [c for c in fields if c.startswith("hldy_")]
    seasons = [c for c in fields if c.startswith("seas_prd_")]
    return {"controls": controls, "holidays": holidays, "seasons": seasons}


def standardize(values: list[float]) -> tuple[list[float], float, float]:
    """Z-scores. Zero variance returns zeros with sd 0.0."""
    n = len(values)
    mean = sum(values) / n
    var = sum((v - mean) ** 2 for v in values) / n
    sd = var**0.5
    if sd == 0:
        return [0.0] * n, mean, 0.0
    return [(v - mean) / sd for v in values], mean, sd


def control_matrix(
    rows: list[dict],
    columns: tuple[str, ...] = CONTROL_COLUMNS,
    stats: dict | None = None,
) -> dict:
    """Standardized control columns.

    Pass train ``stats`` when transforming test/forecast rows so the scale
    matches the fitted model. Returns stats always.
    """
    out: dict = {"columns": list(columns), "stats": {}, "values": []}
    computed: dict = {}
    zcols = {}
    for col in columns:
        vals = [float(r["extras"].get(col) or 0.0) for r in rows]
        if stats is not None and col in stats:
            mean, sd = stats[col]["mean"], stats[col]["sd"]
        else:
            _, mean, sd = standardize(vals)
        computed[col] = {"mean": mean, "sd": sd}
        zcols[col] = [(v - mean) / sd if sd else 0.0 for v in vals]
    out["stats"] = computed
    out["values"] = [[zcols[c][i] for c in columns] for i in range(len(rows))]
    return out


def holiday_flags(extras: dict, holiday_columns: list[str]) -> dict:
    """Bundle sparse holiday dummies: year-end cluster + other."""
    present = {c for c in holiday_columns if str(extras.get(c)) == "1"}
    return {
        "year_end": 1.0 if present & set(YEAR_END_HOLIDAYS) else 0.0,
        "other_holiday": 1.0 if present - set(YEAR_END_HOLIDAYS) else 0.0,
    }


def season_flags(extras: dict, season_columns: list[str]) -> dict:
    """Keep seas_prd_* period dummies only (weekly dummies deferred)."""
    return {c: 1.0 if str(extras.get(c)) == "1" else 0.0 for c in season_columns}


def aux_matrix(rows: list[dict], groups: dict, control_stats: dict | None = None) -> tuple:
    """Standardized controls + bundled holidays + seas_prd (first dropped).

    Returns (matrix, names, control_stats). Pass train control_stats for
    test/forecast rows. Needs numpy; imported lazily so stdlib-only
    paths keep working.
    """
    import numpy as _np

    parts, names = [], []
    stats = control_stats
    if groups["controls"]:
        cm = control_matrix(rows, tuple(groups["controls"]), stats=stats)
        stats = cm["stats"]
        parts.append(_np.asarray(cm["values"], dtype=float))
        names.extend(f"ctrl_{c}" for c in cm["columns"])
    if groups["holidays"]:
        parts.append(
            _np.array(
                [
                    [
                        holiday_flags(r["extras"], groups["holidays"])["year_end"],
                        holiday_flags(r["extras"], groups["holidays"])["other_holiday"],
                    ]
                    for r in rows
                ]
            )
        )
        names.extend(["hol_year_end", "hol_other"])
    seas_cols = groups["seasons"][1:]
    if seas_cols:
        parts.append(
            _np.array(
                [[season_flags(r["extras"], seas_cols)[c] for c in seas_cols] for r in rows]
            )
        )
        names.extend(f"seas_{c}" for c in seas_cols)
    if not parts:
        return None, [], stats
    return _np.hstack(parts), names, stats
