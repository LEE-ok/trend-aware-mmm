"""Trend-aware MMM dashboard (Streamlit).

Thin UI layer per docs/architecture.md: no math here beyond display.
All computation calls into the trend_mmm package.

Run from the repo root:
    streamlit run apps/dashboard/app.py

Expected artifacts (gitignored, produced by the CLI):
    artifacts/scenario_results.json
    artifacts/bayes_summary.json
    artifacts/bayes_trace.nc (optional, enables intervals in what-if)
"""
import json
import sys
from pathlib import Path

import numpy as np
import streamlit as st

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from trend_mmm.data.preprocess import aux_matrix, discover_columns, load_weekly, pearson, summarize  # noqa: E402
from trend_mmm.data.validation import SPEND_COLUMNS  # noqa: E402
from trend_mmm.simulation.evaluate import evaluate, scenario_defs  # noqa: E402
from trend_mmm.simulation.scenarios import historical_ranges  # noqa: E402

CHANNELS = list(SPEND_COLUMNS)
DEFAULT_CSV = ROOT / "data" / "raw" / "data_GIT.csv"
SAMPLE_CSV = ROOT / "data" / "sample" / "marketing.csv"
ART = ROOT / "artifacts"


@st.cache_data
def load_rows(path: str):
    groups = discover_columns(path)
    extras = tuple(groups["controls"] + groups["holidays"] + groups["seasons"])
    rows = load_weekly(path, extra=extras)
    return rows, groups


@st.cache_data
def load_json(path: str):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def csv_path() -> str:
    sidebar = st.sidebar
    sidebar.header("Inputs")
    default = str(DEFAULT_CSV) if DEFAULT_CSV.exists() else str(SAMPLE_CSV)
    return sidebar.text_input("Weekly CSV", value=default)


st.title("Trend-aware MMM: budget simulator")
path = csv_path()

tab_eda, tab_scen, tab_whatif = st.tabs(["EDA", "S0-S4 scenarios", "What-if"])

with tab_eda:
    try:
        rows, _ = load_rows(path)
    except Exception as exc:
        st.error(f"Cannot load CSV: {exc}")
        st.stop()
    info = summarize(rows)
    st.write(f"Weeks: {info['n_weeks']} ({info['start']} -> {info['end']})")
    sales = [r["sales"] for r in rows]
    table = [
        {
            "channel": ch,
            "median": f"{s['median']:,.0f}",
            "min": f"{s['min']:,.0f}",
            "max": f"{s['max']:,.0f}",
            "zero_weeks": s["zero_weeks"],
            "corr_sales": round(pearson([r["spends"][ch] for r in rows], sales), 3),
        }
        for ch, s in info["channels"].items()
    ]
    st.table(table)
    st.caption("Source: retrospective US retail data (docs/data-contract.md v0.2). Correlation is not causation.")

with tab_scen:
    res_path = ART / "scenario_results.json"
    if not res_path.exists():
        st.warning("artifacts/scenario_results.json not found. Run: python -m trend_mmm scenarios ...")
        st.stop()
    results = load_json(str(res_path))
    base = results["S0"]["sales_mean"]
    table = [
        {
            "scenario": name,
            "sales_mean": f"{r['sales_mean']:,.0f}",
            "sales_lo": f"{r['sales_lo']:,.0f}",
            "sales_hi": f"{r['sales_hi']:,.0f}",
            "vs_S0_%": round(100 * (r["sales_mean"] / base - 1), 1),
            "extrapolation": len(r["extrapolation_flags"]),
        }
        for name, r in results.items()
    ]
    st.table(table)
    st.bar_chart({n: r["sales_mean"] for n, r in results.items()})
    st.caption("80% credible intervals. Flagged scenarios left the historical spend range.")

with tab_whatif:
    try:
        rows, groups = load_rows(path)
    except Exception as exc:
        st.error(f"Cannot load CSV: {exc}")
        st.stop()
    st.subheader("Budget allocation (shares of total)")
    raw = {ch: st.slider(ch, 0.0, 1.0, 0.2, 0.01) for ch in CHANNELS}
    tot_share = sum(raw.values())
    if tot_share <= 0:
        st.error("Shares sum to 0.")
        st.stop()
    shares = {ch: v / tot_share for ch, v in raw.items()}
    st.write("Normalized: " + ", ".join(f"{ch}={s:.1%}" for ch, s in shares.items()))
    total = st.number_input("Total budget (13 weeks)", value=16_200_000, step=100_000)
    weeks = st.number_input("Weeks", value=13, step=1)

    summary_path = ART / "bayes_summary.json"
    trace_path = ART / "bayes_trace.nc"
    if not summary_path.exists():
        st.warning("artifacts/bayes_summary.json not found. Run the bayes CLI first.")
        st.stop()
    summary = load_json(str(summary_path))
    params = summary["posterior"]["params"] if "params" in summary["posterior"] else summary["posterior"]
    ec50 = summary.get("ec50") or {}
    if not ec50:
        from trend_mmm.mmm.bayesian import adstock_numpy

        train_full, _ = rows[: len(rows) - 26], rows[len(rows) - 26 :]
        ec50 = {
            ch: float(np.median(adstock_numpy(np.array([r["spends"][ch] for r in train_full]), 0.5)))
            for ch in CHANNELS
        }
    train, _ = rows[: len(rows) - 26], rows[len(rows) - 26 :]
    _, _, train_stats = aux_matrix(train, groups)
    recent = rows[-13:]
    recent_aux, _, _ = aux_matrix(recent, groups, control_stats=train_stats)
    aux_mean = np.asarray(recent_aux, dtype=float).mean(axis=0)
    ranges = historical_ranges(rows, tuple(CHANNELS))

    if trace_path.exists():
        import arviz as az

        idata = az.from_netcdf(str(trace_path))
        post = idata.posterior
        n = post.sizes["chain"] * post.sizes["draw"]
        step = max(1, n // 100)
        flat = {v: post[v].values.reshape(n, -1) for v in post.data_vars}
        draws = []
        for i in range(0, n, step):
            draw = {"intercept": float(flat["intercept"][i, 0])}
            for ch in CHANNELS:
                draw[f"beta_{ch}"] = float(flat[f"beta_{ch}"][i, 0])
                draw[f"decay_{ch}"] = float(flat[f"decay_{ch}"][i, 0])
                draw[f"alpha_{ch}"] = float(flat[f"alpha_{ch}"][i, 0])
            if "gamma" in flat:
                draw["gamma"] = flat["gamma"][i]
            draws.append(draw)
        bundle = {"channels": CHANNELS, "ec50": ec50 or {ch: 1.0 for ch in CHANNELS}}
        if st.button("Evaluate"):
            res = evaluate(draws, bundle, float(total), shares, int(weeks), aux_mean, ranges)
            st.metric("Expected sales", f"{res['sales_mean']:,.0f}")
            st.write(f"80% interval: [{res['sales_lo']:,.0f}, {res['sales_hi']:,.0f}]")
            st.table([{"channel": ch, "ROAS": round(v, 1)} for ch, v in res["roas"].items()])
            if res["extrapolation_flags"]:
                st.warning(f"Extrapolation: {res['extrapolation_flags']}")
    else:
        st.info("No trace found: posterior-mean approximation (no interval).")
        if st.button("Evaluate (approx)"):
            draw = {"intercept": params["intercept"]["mean"]}
            for ch in CHANNELS:
                draw[f"beta_{ch}"] = params[f"beta_{ch}"]["mean"]
                draw[f"decay_{ch}"] = params[f"decay_{ch}"]["mean"]
                draw[f"alpha_{ch}"] = params[f"alpha_{ch}"]["mean"]
            if "gamma" in params and len(params["gamma"]["mean"]) == len(aux_mean):
                draw["gamma"] = np.array(params["gamma"]["mean"])
            else:
                draw["gamma"] = np.zeros(len(aux_mean))
            bundle = {"channels": CHANNELS, "ec50": ec50 or {ch: 1.0 for ch in CHANNELS}}
            res = evaluate([draw], bundle, float(total), shares, int(weeks), aux_mean, ranges)
            st.metric("Expected sales (approx)", f"{res['sales_mean']:,.0f}")
            st.table([{"channel": ch, "ROAS": round(v, 1)} for ch, v in res["roas"].items()])
            if res["extrapolation_flags"]:
                st.warning(f"Extrapolation: {res['extrapolation_flags']}")
