"""Validate the initial weekly CSV contract without third-party dependencies."""
import csv
import math
from datetime import date
from pathlib import Path

SPEND_COLUMNS = ("meta_spend", "google_spend", "naver_spend", "influencer_spend")
REQUIRED_COLUMNS = ("week", "revenue", *SPEND_COLUMNS)


def validate_csv(path: str | Path) -> list[str]:
    errors = []
    dates = []
    seen = set()
    try:
        with Path(path).open(encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream)
            fields = reader.fieldnames or []
            if len(fields) != len(set(fields)):
                return ["Duplicate column names."]
            missing = set(REQUIRED_COLUMNS) - set(fields)
            if missing:
                return [f"Missing columns: {', '.join(sorted(missing))}"]
            count = 0
            for line, row in enumerate(reader, start=2):
                count += 1
                if None in row:
                    errors.append(f"Line {line}: extra values.")
                raw_date = row.get("week") or ""
                try:
                    day = date.fromisoformat(raw_date)
                    if raw_date != day.isoformat():
                        raise ValueError
                    if day in seen:
                        errors.append(f"Line {line}: duplicate week.")
                    seen.add(day)
                    dates.append(day)
                except ValueError:
                    errors.append(f"Line {line}: week must be YYYY-MM-DD.")
                for column in REQUIRED_COLUMNS[1:]:
                    try:
                        value = float(row.get(column) or "")
                        if not math.isfinite(value) or value < 0:
                            raise ValueError
                    except (ValueError, TypeError):
                        errors.append(f"Line {line}: {column} must be finite and non-negative.")
            if not count:
                errors.append("No data rows.")
    except (OSError, UnicodeError, csv.Error) as exc:
        return [f"Cannot read CSV: {exc}"]
    if dates != sorted(dates):
        errors.append("Weeks must be in ascending order.")
    for previous, current in zip(sorted(seen), sorted(seen)[1:]):
        if (current - previous).days != 7:
            errors.append(f"Weekly gap or inconsistent weekday: {previous} -> {current}.")
    return errors

