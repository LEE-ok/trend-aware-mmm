"""Local, aggregate-only export. Never trains, edits the source, or replaces output."""
import argparse
import hashlib
import json
import math
import re
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path

WEB = Path(__file__).resolve().parents[1]
ROOT = WEB.parents[1]
sys.path.insert(0, str(ROOT / "src"))
from trend_mmm.data.preprocess import load_weekly, pearson, time_split
from trend_mmm.data.validation import SPEND_COLUMNS

LABELS = ["DM · 우편", "SO · 소셜", "VIDTR · TV", "VIDDIG · 디지털 영상", "SEM · 검색"]


def quantile(values, p):
    ordered = sorted(values)
    index = (len(ordered) - 1) * p
    low, high = math.floor(index), math.ceil(index)
    return ordered[low] + (ordered[high] - ordered[low]) * (index - low)


def stats(values):
    return {"total": math.fsum(values), "mean": statistics.mean(values),
            "min": min(values), "q25": quantile(values, .25),
            "median": statistics.median(values), "q75": quantile(values, .75), "max": max(values)}


def ranks(values):
    ordered = sorted(range(len(values)), key=values.__getitem__)
    result = [0.0] * len(values)
    start = 0
    while start < len(values):
        end = start + 1
        while end < len(values) and values[ordered[end]] == values[ordered[start]]:
            end += 1
        for index in ordered[start:end]:
            result[index] = (start + 1 + end) / 2
        start = end
    return result


def numeric_cells(line):
    return [float(v.strip().replace("**", "").replace(",", "")) for v in line.split("|")[2:-1]]


def document_models():
    text = (ROOT / "docs/bayes-run.md").read_text(encoding="utf-8").split("## 최종 확정런 — 2026-10-12", 1)[1]
    fields = {"test_mape": "test MAPE", "direction_accuracy": "test 방향정확도", "max_rhat": "max R-hat"}
    records = [{"id": "base", "label": "Bayesian 기본"}, {"id": "trend", "label": "트렌드 결합"}]
    for key, label in fields.items():
        line = next(line for line in text.splitlines() if line.startswith(f"| {label} |"))
        for record, value in zip(records, numeric_cells(line), strict=True):
            record[key] = value
    return {"source": "docs/bayes-run.md", "run_date": "2026-10-12", "provenance": "document_recorded", "trace_verified": False, "models": records}


def compare_document(sales, channels):
    text = (ROOT / "docs/eda.md").read_text(encoding="utf-8")
    checks = []

    def compare(label, actual, recorded, tolerance):
        checks.append({"metric": label, "computed": actual, "recorded": recorded,
                       "tolerance": tolerance, "matches": abs(actual - recorded) <= tolerance})

    match = re.search(r"sales: 중앙값 ([\d,]+) / 최소 ([\d,]+) / 최대 ([\d,]+)", text)
    if not match:
        raise ValueError("EDA sales reference is missing")
    for key, value in zip(["median", "min", "max"], match.groups(), strict=True):
        compare("sales." + key, sales[key], float(value.replace(",", "")), .5)
    for ch in channels:
        line = next(line for line in text.splitlines() if line.startswith(f"| {ch['id']} |"))
        for key, value in zip(["median", "min", "max", "zero_weeks", "pearson"], numeric_cells(line), strict=True):
            actual = ch[key] if key in ["zero_weeks", "pearson"] else ch["spend"][key]
            compare(ch["id"] + "." + key, actual, value, .0005 if key == "pearson" else (0 if key == "zero_weeks" else .5))
        # The later comparison table records Pearson and Spearman separately.
        pattern = rf"\| {ch['id']} \| (0\.\d+) \| (0\.\d+) \|"
        reference = re.search(pattern, text)
        if not reference:
            raise ValueError("EDA correlation reference is missing: " + ch["id"])
        compare(ch["id"] + ".spearman", ch["spearman"], float(reference.group(2)), .0005)
    sem = next(ch for ch in channels if ch['id'] == 'mdsp_sem')
    approximate = re.search(r"중앙값은 약 ([\d.]+)만이며, 중앙 50%는 약 ([\d.]+)만~([\d.]+)만", text)
    if not approximate:
        raise ValueError('SEM prose reference is missing')
    for key, value in zip(['median', 'q25', 'q75'], approximate.groups(), strict=True):
        compare('mdsp_sem.prose.' + key, sem['spend'][key], float(value) * 10000, 500)
    return {"source": "docs/eda.md", "provenance": "document_comparison", "rounding_note": "정수 USD ±0.5, 상관계수 ±0.0005, 서술형 근사 만 단위 ±500 USD로 대조합니다.",
            "checks": checks, "mismatch_count": sum(not c["matches"] for c in checks)}


def aggregate():
    source = ROOT / "data/raw/data_GIT.csv"
    before = hashlib.sha256(source.read_bytes()).hexdigest()
    rows = load_weekly(source)
    train, test = time_split(rows, 26)
    sales = stats([r["sales"] for r in rows])
    spend_total = math.fsum(r["spends"][ch] for r in rows for ch in SPEND_COLUMNS)
    channels = []
    y = [r["sales"] for r in rows]
    for ch, label in zip(SPEND_COLUMNS, LABELS, strict=True):
        x = [r["spends"][ch] for r in rows]
        spend = stats(x)
        channels.append({"id": ch, "label": label, "spend": spend, "share": spend["total"] / spend_total,
                         "pearson": pearson(x, y), "spearman": pearson(ranks(x), ranks(y)), "zero_weeks": x.count(0)})
    document_comparison = compare_document(sales, channels)
    if hashlib.sha256(source.read_bytes()).hexdigest() != before:
        raise ValueError("Source changed during aggregation")
    return {
        "schema_version": "1.0.0", "source": "data/raw/data_GIT.csv", "source_sha256": before,
        "generated_at": datetime.now(timezone.utc).isoformat(), "provenance": "csv_computed", "currency": "USD",
        "period": {"start": rows[0]["date"].isoformat(), "end": rows[-1]["date"].isoformat(), "frequency": "weekly"},
        "validation_status": "passed", "summary": {"weeks": len(rows), "train_weeks": len(train), "test_weeks": len(test), "channel_count": len(channels), "spend_total": spend_total},
        "privacy": {"scope": "aggregate_only", "weekly_rows_exported": False, "weekly_series_enabled": False, "raw_publication_approved": False, "distribution_method": "linear_quantiles"},
        "sales": sales, "channels": channels, "document_comparison": document_comparison,
        "model_performance": document_models(),
        "availability": {"raw_csv": True, "trace": (ROOT / "artifacts/bayes_trace.nc").is_file(), "model_summary": (ROOT / "artifacts/bayes_summary.json").is_file(), "trend_csv": (ROOT / "data/raw/trends_google.csv").is_file(), "scenario_results": (ROOT / "artifacts/scenario_results.json").is_file(), "optimum_results": any((ROOT / "artifacts").glob("optimum_draws*.json"))},
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=WEB / "data/dashboard-aggregates.json")
    args = parser.parse_args()
    payload = aggregate()
    import jsonschema
    schema = json.loads((WEB / "data/dashboard.schema.json").read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator(schema, format_checker=jsonschema.FormatChecker()).validate(payload)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(payload, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")
    print("Aggregate-only export created; schema passed; document mismatches:", payload["document_comparison"]["mismatch_count"])
