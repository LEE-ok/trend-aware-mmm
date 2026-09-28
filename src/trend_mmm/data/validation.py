"""Validate the weekly CSV contract (v0.2) without third-party dependencies.

Contract v0.2: data_GIT.csv based retrospective simulation.
Required: wk_strt_dt, sales, mdsp_dm, mdsp_so, mdsp_vidtr, mdsp_viddig, mdsp_sem.
Extra columns (other mdsp_*/mdip_*, me_*, mrkdn_*, hldy_*, seas_*) are allowed
and ignored by the validator. va_pub_* columns are allowed by the validator
but excluded from modeling until their meaning is confirmed.
"""
import csv
import math
from datetime import date
from pathlib import Path

DATE_COLUMN = "wk_strt_dt"
TARGET_COLUMN = "sales"
SPEND_COLUMNS = ("mdsp_dm", "mdsp_so", "mdsp_vidtr", "mdsp_viddig", "mdsp_sem")
REQUIRED_COLUMNS = (DATE_COLUMN, TARGET_COLUMN, *SPEND_COLUMNS)


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
                raw_date = row.get(DATE_COLUMN) or ""
                try:
                    day = date.fromisoformat(raw_date)
                    if raw_date != day.isoformat():
                        raise ValueError
                    if day in seen:
                        errors.append(f"Line {line}: duplicate week.")
                    seen.add(day)
                    dates.append(day)
                except ValueError:
                    errors.append(f"Line {line}: {DATE_COLUMN} must be YYYY-MM-DD.")
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

