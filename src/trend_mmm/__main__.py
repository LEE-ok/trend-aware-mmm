import argparse
import json
from pathlib import Path

import numpy as np

from .data.preprocess import (
    control_matrix,
    discover_columns,
    holiday_flags,
    load_weekly,
    pearson,
    season_flags,
    summarize,
    time_split,
)
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


def _aux_matrix(rows, groups):
    """Standardized controls + bundled holidays + seas_prd (first dropped)."""
    parts, names = [], []
    if groups["controls"]:
        cm = control_matrix(rows, tuple(groups["controls"]))
        parts.append(np.asarray(cm["values"], dtype=float))
        names.extend(f"ctrl_{c}" for c in cm["columns"])
    hol = np.array(
        [
            [holiday_flags(r["extras"], groups["holidays"])["year_end"],
             holiday_flags(r["extras"], groups["holidays"])["other_holiday"]]
            for r in rows
        ]
    )
    if groups["holidays"]:
        parts.append(hol)
        names.extend(["hol_year_end", "hol_other"])
    seas_cols = groups["seasons"][1:]
    if seas_cols:
        parts.append(
            np.array(
                [[season_flags(r["extras"], seas_cols)[c] for c in seas_cols] for r in rows]
            )
        )
        names.extend(f"seas_{c}" for c in seas_cols)
    if not parts:
        return None, []
    return np.hstack(parts), names


def cmd_bayes(args):
    from .mmm.bayesian import fit_bayesian, predict_posterior_mean, summarize_posterior

    groups = discover_columns(args.path)
    extras = tuple(groups["controls"] + groups["holidays"] + groups["seasons"])
    rows = load_weekly(args.path, extra=extras)
    train, test = time_split(rows, test_weeks=args.test_weeks)
    train_aux, aux_names = _aux_matrix(train, groups)
    test_aux, _ = _aux_matrix(test, groups)
    idata, bundle = fit_bayesian(
        train, SPEND_COLUMNS, aux=train_aux,
        draws=args.draws, tune=args.tune, chains=args.chains,
    )
    train_pred = predict_posterior_mean(idata, bundle, train, train_aux)
    test_pred = predict_posterior_mean(idata, bundle, test, test_aux)
    train_m = metrics([r["sales"] for r in train], train_pred.tolist())
    test_m = metrics([r["sales"] for r in test], test_pred.tolist())
    summary = summarize_posterior(idata, SPEND_COLUMNS)
    print(f"test({len(test)}w): " + _fmt(test_m))
    print(f"max_rhat={summary['max_rhat']:.3f}")
    for ch in SPEND_COLUMNS:
        p = summary["params"]
        print(
            f"{ch}: beta={p[f'beta_{ch}']['mean']:,.0f} "
            f"decay={p[f'decay_{ch}']['mean']:.2f} alpha={p[f'alpha_{ch}']['mean']:.2f}"
        )
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    try:
        idata.to_netcdf(str(out / "bayes_trace.nc"))
    except Exception as exc:  # missing netCDF backend: trace skipped, summary still saved
        print(f"trace save skipped: {exc}")
        idata.to_json(str(out / "bayes_trace.json")) if hasattr(idata, "to_json") else None
    payload = {
        "settings": {"draws": args.draws, "tune": args.tune, "chains": args.chains,
                     "test_weeks": args.test_weeks, "aux_columns": aux_names},
        "posterior": summary,
        "train_metrics": train_m,
        "test_metrics": test_m,
        "assumptions": [
            "ec50 fixed at train median (priors v1.0)",
            "controls standardized; forecast holds recent-13w mean (retrospective run uses actuals)",
            "holidays bundled year-end/other; seas_prd first dummy dropped",
        ],
    }
    (out / "bayes_summary.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"saved: {out / 'bayes_summary.json'}")


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
    bayes = sub.add_parser("bayes")
    bayes.add_argument("path")
    bayes.add_argument("--test-weeks", type=int, default=26)
    bayes.add_argument("--draws", type=int, default=500)
    bayes.add_argument("--tune", type=int, default=500)
    bayes.add_argument("--chains", type=int, default=2)
    bayes.add_argument("--out", default="artifacts")
    bayes.set_defaults(func=cmd_bayes)
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
