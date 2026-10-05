"""Google Trends retail-demand series (pandas + pytrends).

Reproducibility notes (see docs/trends.md):
- Values are 0-100 relative to the request window maximum, resampled by
  Google per request. Exact values may shift between fetches; the series
  shape (seasonality, spikes) is stable.
- Weekly grain, Sunday-start dates matching data_GIT.csv weeks.
- Composite TREND_KEYWORDS exclude 'christmas': holiday spikes are already
  covered by the bundled holiday flags.
"""
import csv
from datetime import date
from pathlib import Path

TREND_KEYWORDS = ("sale", "deals", "coupons", "gift")
TIMEFRAME = "2014-08-03 2018-07-29"
GEO = "US"


def fetch(keywords=TREND_KEYWORDS, timeframe=TIMEFRAME, geo=GEO):
    """Fetch weekly interest. Returns a pandas DataFrame (date index)."""
    from pytrends.request import TrendReq

    req = TrendReq(hl="en-US", tz=360, timeout=(10, 25))
    req.build_payload(list(keywords), timeframe=timeframe, geo=geo)
    frame = req.interest_over_time()
    if "isPartial" in frame.columns:
        frame = frame.drop(columns=["isPartial"])
    return frame


def save_weekly_csv(frame, path: str | Path) -> None:
    """Write wk_strt_dt + one column per keyword."""
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    dates = [d.date().isoformat() for d in frame.index]
    with out.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["wk_strt_dt", *frame.columns])
        for day, (_, row) in zip(dates, frame.iterrows()):
            writer.writerow([day, *[int(v) for v in row]])


def load_series(path: str | Path, columns=None) -> dict:
    """Read a saved trend CSV. Returns {column: [(date, value)]}."""
    series: dict = {}
    with Path(path).open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        fields = reader.fieldnames or []
        cols = list(columns) if columns else [c for c in fields if c != "wk_strt_dt"]
        for col in cols:
            if col not in fields:
                raise ValueError(f"Missing trend column: {col}.")
        data = {col: [] for col in cols}
        for row in reader:
            day = date.fromisoformat(row["wk_strt_dt"])
            for col in cols:
                data[col].append((day, float(row[col])))
    return data


def composite(data: dict) -> list[tuple]:
    """Mean of per-keyword z-scores, aligned on shared dates."""
    import statistics

    common = set.intersection(*[set(d for d, _ in vals) for vals in data.values()])
    days = sorted(common)
    lookup = {col: dict(vals) for col, vals in data.items()}
    cols = sorted(data)
    zcols = {}
    for col in cols:
        vals = [lookup[col][d] for d in days]
        mu = statistics.mean(vals)
        sd = statistics.pstdev(vals) or 1.0
        zcols[col] = [(v - mu) / sd for v in vals]
    return [(day, sum(zcols[col][i] for col in cols) / len(cols)) for i, day in enumerate(days)]


def trend_zscores(train_days: list, test_days: list, path: str | Path) -> tuple:
    """Composite trend aligned to row dates, standardized on train.

    Returns (train_z, test_z, mean, sd). Raises KeyError on missing weeks.
    """
    import statistics

    data = load_series(path, columns=list(TREND_KEYWORDS))
    comp = dict(composite(data))
    train_vals = [comp[d] for d in train_days]
    mu = statistics.mean(train_vals)
    sd = statistics.pstdev(train_vals) or 1.0
    return (
        [(v - mu) / sd for v in train_vals],
        [(comp[d] - mu) / sd for d in test_days],
        mu,
        sd,
    )
