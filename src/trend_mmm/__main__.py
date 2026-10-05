import argparse
import json
from pathlib import Path

import numpy as np

from .data.preprocess import (
    aux_matrix,
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


def cmd_trends_fetch(args):
    from .trends.google import TREND_KEYWORDS, fetch, save_weekly_csv

    frame = fetch()
    save_weekly_csv(frame, args.out)
    print(f"weeks: {len(frame)}, keywords: {list(TREND_KEYWORDS)}")
    print(f"saved: {args.out}")


def _aux_matrix(rows, groups, control_stats=None):
    """Stable-order aux matrix shared by train and forecast paths."""
    return aux_matrix(rows, groups, control_stats=control_stats)


def _hstack_col(matrix, column, nrows):
    """Append one column, creating the matrix when no other aux exists."""
    col = np.asarray(column, dtype=float).reshape(nrows, 1)
    if matrix is None:
        return col
    return np.hstack([np.asarray(matrix, dtype=float), col])


def cmd_bayes(args):
    from .mmm.bayesian import fit_bayesian, predict_posterior_mean, summarize_posterior

    groups = discover_columns(args.path)
    extras = tuple(groups["controls"] + groups["holidays"] + groups["seasons"])
    rows = load_weekly(args.path, extra=extras)
    train, test = time_split(rows, test_weeks=args.test_weeks)
    train_aux, aux_names, train_stats = _aux_matrix(train, groups)
    test_aux, _, _ = _aux_matrix(test, groups, control_stats=train_stats)
    if args.trend:
        from .trends.google import trend_zscores

        trz, tez, _, _ = trend_zscores(
            [r["date"] for r in train], [r["date"] for r in test], args.trend
        )
        train_aux = _hstack_col(train_aux, trz, len(train))
        test_aux = _hstack_col(test_aux, tez, len(test))
        aux_names = [*aux_names, "trend_demand"]
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
        "ec50": bundle["ec50"],
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


def cmd_scenarios(args):
    import arviz as az

    from .simulation.evaluate import evaluate, marginal_roas, scenario_defs

    groups = discover_columns(args.path)
    extras = tuple(groups["controls"] + groups["holidays"] + groups["seasons"])
    rows = load_weekly(args.path, extra=extras)
    train, _ = time_split(rows, test_weeks=26)
    _, _, train_stats = _aux_matrix(train, groups)
    recent = rows[-args.weeks :]
    total = sum(sum(r["spends"][ch] for ch in SPEND_COLUMNS) for r in recent)
    recent_aux, _, _ = _aux_matrix(recent, groups, control_stats=train_stats)
    aux_mean = np.asarray(recent_aux, dtype=float).mean(axis=0)
    if args.trend:
        from .trends.google import trend_zscores

        trz, _, _, _ = trend_zscores(
            [r["date"] for r in train], [r["date"] for r in recent], args.trend
        )
        level = args.trend_level
        if level == "mean":
            tval = float(np.mean(trz[-args.weeks :]))
        elif level == "low":
            tval = float(np.percentile(trz, 10))
        elif level == "high":
            tval = float(np.percentile(trz, 90))
        else:
            raise ValueError("--trend-level must be mean, low or high.")
        aux_mean = np.append(np.asarray(aux_mean, dtype=float), tval)
        print(f"trend_demand level={level} value={tval:.3f}")
    from .simulation.scenarios import historical_ranges as _ranges

    ranges = _ranges(rows, SPEND_COLUMNS)
    idata = az.from_netcdf(args.trace)
    post = idata.posterior
    n = post.sizes["chain"] * post.sizes["draw"]
    draws = []
    flat = {v: post[v].values.reshape(n, -1) for v in post.data_vars}
    for i in range(n):
        draw = {}
        for ch in SPEND_COLUMNS:
            draw[f"beta_{ch}"] = float(flat[f"beta_{ch}"][i, 0])
            draw[f"decay_{ch}"] = float(flat[f"decay_{ch}"][i, 0])
            draw[f"alpha_{ch}"] = float(flat[f"alpha_{ch}"][i, 0])
        draw["intercept"] = float(flat["intercept"][i, 0])
        if "gamma" in flat:
            draw["gamma"] = flat["gamma"][i]
        draws.append(draw)
    if draws and "gamma" in draws[0] and len(draws[0]["gamma"]) != len(aux_mean):
        raise ValueError(
            f"Trace gamma dim {len(draws[0]['gamma'])} != aux dim {len(aux_mean)}. "
            "Use a trend-aware trace with --trend (or no --trend with a base trace)."
        )
    bundle = json.loads(
        Path(args.trace).with_name("bayes_summary.json").read_text(encoding="utf-8")
        if Path(args.trace).with_name("bayes_summary.json").exists()
        else '{"ec50": {}}'
    )
    ec50 = bundle.get("ec50", {})
    if not ec50:
        feats = {ch: np.array([r["spends"][ch] for r in train]) for ch in SPEND_COLUMNS}
        from .mmm.bayesian import adstock_numpy

        ec50 = {ch: float(np.median(adstock_numpy(feats[ch], 0.5))) for ch in SPEND_COLUMNS}
    results = {}
    for name, shares in scenario_defs().items():
        res = evaluate(
            draws, {"channels": list(SPEND_COLUMNS), "ec50": ec50},
            total, shares, args.weeks, aux_mean, ranges,
        )
        res["marginal_roas"] = {
            ch: marginal_roas(
                draws, {"channels": list(SPEND_COLUMNS), "ec50": ec50},
                total, shares, args.weeks, aux_mean, ch,
            )
            for ch in SPEND_COLUMNS
        }
        results[name] = res
        print(
            f"{name}: sales={res['sales_mean']:,.0f} "
            f"[{res['sales_lo']:,.0f}, {res['sales_hi']:,.0f}] "
            f"flags={len(res['extrapolation_flags'])}"
        )
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"saved: {args.out}")


def cmd_optimize(args):
    from .optimization.allocate import optimize
    from .simulation.evaluate import evaluate
    from .simulation.scenarios import check_extrapolation, historical_ranges, scenario_spends

    summary = json.loads(Path(args.summary).read_text(encoding="utf-8"))
    params = summary["posterior"]["params"]
    ec50 = summary.get("ec50") or {}
    groups = discover_columns(args.path)
    extras = tuple(groups["controls"] + groups["holidays"] + groups["seasons"])
    rows = load_weekly(args.path, extra=extras)
    train, _ = time_split(rows, test_weeks=26)
    if not ec50:
        from .mmm.bayesian import adstock_numpy

        ec50 = {
            ch: float(np.median(adstock_numpy(np.array([r["spends"][ch] for r in train]), 0.5)))
            for ch in SPEND_COLUMNS
        }
    train_aux, _, train_stats = _aux_matrix(train, groups)
    recent = rows[-args.weeks :]
    recent_aux, _, _ = _aux_matrix(recent, groups, control_stats=train_stats)
    aux_mean = np.asarray(recent_aux, dtype=float).mean(axis=0)
    draw = {"intercept": params["intercept"]["mean"]}
    for ch in SPEND_COLUMNS:
        draw[f"beta_{ch}"] = params[f"beta_{ch}"]["mean"]
        draw[f"decay_{ch}"] = params[f"decay_{ch}"]["mean"]
        draw[f"alpha_{ch}"] = params[f"alpha_{ch}"]["mean"]
    if "gamma" in params and len(params["gamma"]["mean"]) == len(aux_mean):
        draw["gamma"] = np.array(params["gamma"]["mean"])
    else:
        draw["gamma"] = np.zeros(len(aux_mean))
    if args.bounds:
        bounds = {ch: tuple(v) for ch, v in json.loads(args.bounds).items()}
    else:
        bounds = {ch: (0.0, 0.6) for ch in SPEND_COLUMNS}
    bundle = {"channels": list(SPEND_COLUMNS), "ec50": ec50}
    res = optimize(draw, bundle, args.total, args.weeks, aux_mean, bounds)
    spends = scenario_spends(args.total, res["shares"], args.weeks)
    flags = check_extrapolation(spends, historical_ranges(rows, SPEND_COLUMNS))
    print("shares: " + ", ".join(f"{ch}={s:.1%}" for ch, s in res["shares"].items()))
    print(f"sales={res['sales']:,.0f} iters={res['iters']} flags={len(flags)}")
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(
            {"shares": res["shares"], "sales": res["sales"],
             "marginal_roas": res["marginal_roas"], "iters": res["iters"],
             "bounds": bounds, "extrapolation_flags": flags,
             "note": "posterior-mean optimum; intervals need trace draws"},
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"saved: {args.out}")


def cmd_retrieve_index(args):
    from .retrieval.store import TrendStore
    from .trends.collect import clean_docs, collect_csv

    docs = clean_docs(collect_csv(args.path))
    store = TrendStore(args.store)
    n = store.add(docs)
    print(f"indexed: {n}, total: {store.count()}")


def cmd_retrieve_search(args):
    from .retrieval.store import TrendStore

    store = TrendStore(args.store)
    for hit in store.search(args.query, args.available_before, args.category, args.n):
        print(
            f"{hit['distance']:.3f} [{hit['category']}] {hit['source_url']} "
            f"(collected {hit['collected_at']})"
        )


def cmd_workflow_trends(args):
    from .workflows.graph import run_trends_pipeline

    state = run_trends_pipeline(args.source, args.out, kind=args.kind)
    print(f"weeks: {len(state['weekly'])}, saved: {state['saved']}")


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
    fetch = sub.add_parser("trends-fetch")
    fetch.add_argument("--out", default="data/raw/trends_google.csv")
    fetch.set_defaults(func=cmd_trends_fetch)
    bayes = sub.add_parser("bayes")
    bayes.add_argument("path")
    bayes.add_argument("--test-weeks", type=int, default=26)
    bayes.add_argument("--draws", type=int, default=500)
    bayes.add_argument("--tune", type=int, default=500)
    bayes.add_argument("--chains", type=int, default=2)
    bayes.add_argument("--out", default="artifacts")
    bayes.add_argument("--trend", default=None)
    bayes.set_defaults(func=cmd_bayes)
    scen = sub.add_parser("scenarios")
    scen.add_argument("path")
    scen.add_argument("--trace", required=True)
    scen.add_argument("--weeks", type=int, default=13)
    scen.add_argument("--out", default="artifacts/scenario_results.json")
    scen.add_argument("--trend", default=None)
    scen.add_argument("--trend-level", default="mean")
    scen.set_defaults(func=cmd_scenarios)
    opt = sub.add_parser("optimize")
    opt.add_argument("path")
    opt.add_argument("--summary", required=True)
    opt.add_argument("--total", type=float, required=True)
    opt.add_argument("--weeks", type=int, default=13)
    opt.add_argument("--bounds", default=None)
    opt.add_argument("--out", default="artifacts/optimum.json")
    opt.set_defaults(func=cmd_optimize)
    idx = sub.add_parser("retrieve-index")
    idx.add_argument("path")
    idx.add_argument("--store", default="artifacts/chroma")
    idx.set_defaults(func=cmd_retrieve_index)
    sea = sub.add_parser("retrieve-search")
    sea.add_argument("query")
    sea.add_argument("--store", default="artifacts/chroma")
    sea.add_argument("--available-before", default=None)
    sea.add_argument("--category", default=None)
    sea.add_argument("--n", type=int, default=5)
    sea.set_defaults(func=cmd_retrieve_search)
    wf = sub.add_parser("workflow-trends")
    wf.add_argument("source")
    wf.add_argument("--out", required=True)
    wf.add_argument("--kind", default="docs-csv")
    wf.set_defaults(func=cmd_workflow_trends)
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
