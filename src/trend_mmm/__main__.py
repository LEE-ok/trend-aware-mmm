import argparse
import json
from pathlib import Path

from .data.preprocess import load_weekly, pearson, summarize, time_split
from .data.validation import SPEND_COLUMNS, validate_csv
from .mmm.baseline import fit_baseline, metrics, predict
from .trends.collect import aggregate_weekly, clean_docs, collect_csv


def cmd_validate(args):
    errors = validate_csv(args.path)
    if errors:
        for error in errors:
            print(error)
        raise SystemExit(1)
    print("PASS: weekly schema checks passed; model suitability is not assessed.")


def cmd_eda(args):
    rows = load_weekly(args.path)
    info = summarize(rows)
    sales = [r["sales"] for r in rows]
    print(f"weeks: {info['n_weeks']} ({info['start']} -> {info['end']})")
    s = info["sales"]
    print(f"sales: median={s['median']:,.0f} min={s['min']:,.0f} max={s['max']:,.0f}")
    for ch, stats in info["channels"].items():
        corr = pearson([r["spends"][ch] for r in rows], sales)
        print(
            f"{ch}: median={stats['median']:,.0f} "
            f"min={stats['min']:,.0f} max={stats['max']:,.0f} "
            f"zero_weeks={stats['zero_weeks']} corr_sales={corr:.3f}"
        )


def cmd_baseline(args):
    rows = load_weekly(args.path)
    train, test = time_split(rows, test_weeks=args.test_weeks)
    model = fit_baseline(train, SPEND_COLUMNS)
    train_pred = predict(model, train, SPEND_COLUMNS)
    test_pred = predict(model, test, SPEND_COLUMNS)
    train_m = metrics([r["sales"] for r in train], train_pred)
    test_m = metrics([r["sales"] for r in test], test_pred)
    print(f"grid: decay={model['decay']} alpha={model['alpha']}")
    print(f"train({len(train)}w): " + _fmt(train_m))
    print(f"test({len(test)}w): " + _fmt(test_m))
    print("coefs: " + ", ".join(f"{ch}={model['coefs'][ch]:+.3f}" for ch in SPEND_COLUMNS))
    if args.out:
        out = Path(args.out)
        out.mkdir(parents=True, exist_ok=True)
        payload = {
            "model": {**model, "ec50": model["ec50"]},
            "train_metrics": train_m,
            "test_metrics": test_m,
            "train_weeks": len(train),
            "test_weeks": len(test),
            "channels": list(SPEND_COLUMNS),
        }
        (out / "baseline_model.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print(f"saved: {out / 'baseline_model.json'}")


def _fmt(m):
    return f"MAPE={m['mape']:.4f} RMSE={m['rmse']:,.0f} MAE={m['mae']:,.0f} dir_acc={m['dir_acc']:.3f}"


def cmd_trends(args):
    docs = clean_docs(collect_csv(args.path))
    weekly = aggregate_weekly(docs)
    print(f"docs: {len(docs)}, weeks: {len(weekly)}")
    for week in sorted(weekly):
        cell = weekly[week]
        print(f"{week}: n={cell['n_docs']} mean_score={cell['mean_score']:.3f}")


def main():
    parser = argparse.ArgumentParser(description="Trend-aware MMM commands")
    sub = parser.add_subparsers(dest="command", required=True)
    validate = sub.add_parser("validate")
    validate.add_argument("path")
    validate.set_defaults(func=cmd_validate)
    eda = sub.add_parser("eda")
    eda.add_argument("path")
    eda.set_defaults(func=cmd_eda)
    baseline = sub.add_parser("baseline")
    baseline.add_argument("path")
    baseline.add_argument("--test-weeks", type=int, default=26)
    baseline.add_argument("--out", default="artifacts")
    baseline.set_defaults(func=cmd_baseline)
    trends = sub.add_parser("trends")
    trends.add_argument("path")
    trends.set_defaults(func=cmd_trends)
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
