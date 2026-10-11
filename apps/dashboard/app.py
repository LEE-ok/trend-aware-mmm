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


SERIES_1, SERIES_2, INK = "#2a78d6", "#eb6834", "#898781"


def interval_chart(results: dict) -> dict:
    """Scenario mean + 80% interval against the S0 band (Vega-Lite spec, 1e8 USD)."""
    s0 = results["S0"]
    rows = [
        {
            "scenario": name,
            "mean": r["sales_mean"] / 1e8,
            "lo": r["sales_lo"] / 1e8,
            "hi": r["sales_hi"] / 1e8,
            "range": "extrapolated" if r["extrapolation_flags"] else "within observed spend",
        }
        for name, r in results.items()
    ]
    x = {"field": "scenario", "type": "nominal", "sort": None, "title": None, "axis": {"labelAngle": 0}}
    y = {"type": "quantitative", "scale": {"zero": False}, "title": "13-week sales (100M USD)"}
    tip = [
        {"field": "scenario"},
        {"field": "mean", "format": ".2f"},
        {"field": "lo", "format": ".2f", "title": "80% low"},
        {"field": "hi", "format": ".2f", "title": "80% high"},
        {"field": "range"},
    ]
    return {
        "height": 340,
        "layer": [
            {
                "data": {"values": [{"lo": s0["sales_lo"] / 1e8, "hi": s0["sales_hi"] / 1e8}]},
                "mark": {"type": "rect", "color": INK, "opacity": 0.15},
                "encoding": {"y": {"field": "lo", **y}, "y2": {"field": "hi"}},
            },
            {
                "data": {"values": rows},
                "mark": {"type": "rule", "strokeWidth": 2, "color": SERIES_1},
                "encoding": {"x": x, "y": {"field": "lo", **y}, "y2": {"field": "hi"}, "tooltip": tip},
            },
            {
                "data": {"values": rows},
                "mark": {"type": "point", "size": 90, "color": SERIES_1, "strokeWidth": 2},
                "encoding": {
                    "x": x,
                    "y": {"field": "mean", **y},
                    "fill": {
                        "field": "range", "type": "nominal", "title": None,
                        "scale": {
                            "domain": ["within observed spend", "extrapolated"],
                            "range": [SERIES_1, "white"],
                        },
                        "legend": {"orient": "top", "symbolStrokeColor": SERIES_1, "symbolStrokeWidth": 2},
                    },
                    "tooltip": tip,
                },
            },
        ],
    }


def shares_chart(opt: dict) -> dict:
    """Recommended share per channel, current S0 share and the per-draw 80% range."""
    from trend_mmm.simulation.evaluate import BASE_SHARES

    best, each = opt["expected_optimum"]["shares"], opt["per_draw_optimum"]["shares_interval"]
    rows = [
        {
            "channel": ch.replace("mdsp_", ""),
            "recommended": 100 * best[ch],
            "current": 100 * BASE_SHARES[ch],
            "lo": 100 * each[ch][0],
            "hi": 100 * each[ch][1],
        }
        for ch in best
    ]
    x = {"field": "channel", "type": "nominal", "sort": None, "title": None, "axis": {"labelAngle": 0}}
    y = {"type": "quantitative", "title": "Share of budget (%)"}
    tip = [
        {"field": "channel"},
        {"field": "recommended", "format": ".1f"},
        {"field": "current", "format": ".1f", "title": "current (S0)"},
        {"field": "lo", "format": ".1f", "title": "per-draw 80% low"},
        {"field": "hi", "format": ".1f", "title": "per-draw 80% high"},
    ]
    names = ["recommended", "current (S0)", "per-draw 80% range"]
    color = {"scale": {"domain": names, "range": [SERIES_1, SERIES_2, INK]}, "title": None, "legend": {"orient": "top"}}
    return {
        "height": 340,
        "data": {"values": rows},
        "layer": [
            {
                "mark": {"type": "bar", "width": {"band": 0.5}, "cornerRadiusEnd": 4},
                "encoding": {"x": x, "y": {"field": "recommended", **y}, "color": {"datum": names[0], **color},
                             "tooltip": tip},
            },
            {
                "mark": {"type": "rule", "strokeWidth": 2},
                "encoding": {"x": x, "y": {"field": "lo", **y}, "y2": {"field": "hi"},
                             "color": {"datum": names[2], **color}, "tooltip": tip},
            },
            {
                "mark": {"type": "tick", "thickness": 3, "width": {"band": 0.7}},
                "encoding": {"x": x, "y": {"field": "current", **y}, "color": {"datum": names[1], **color},
                             "tooltip": tip},
            },
        ],
    }


st.set_page_config(page_title="Trend-aware MMM", layout="wide")
st.title("Trend-aware MMM: budget simulator")
path = csv_path()
if (ART / "bayes_summary.json").exists():
    _fit = load_json(str(ART / "bayes_summary.json"))
    _rhat = _fit["posterior"]["max_rhat"]
    st.sidebar.header("Model")
    st.sidebar.metric("Test MAPE", f"{_fit['test_metrics']['mape']:.3f}")
    st.sidebar.metric("Max R-hat", f"{_rhat:.3f}", "below 1.01" if _rhat < 1.01 else "above 1.01",
                      delta_color="normal" if _rhat < 1.01 else "inverse")
    st.sidebar.caption(
        f"{_fit['settings']['chains']} chains, {_fit['settings']['draws']} draws. "
        "All intervals are 80% credible intervals."
    )

tab_eda, tab_opt, tab_chat, tab_scen, tab_whatif, tab_curve = st.tabs(
    ["EDA", "Optimum", "Chat", "S0-S4 scenarios", "What-if", "Response curves"]
)

with tab_chat:
    from trend_mmm.workflows.chat import ChatContext, ask, load_env

    load_env(ROOT / ".env")
    st.caption(
        "Answers come from the saved model results through tool calls (summary, scenarios, optimum, "
        "what-if, trend document search). Needs ANTHROPIC_API_KEY in .env."
    )
    log = st.session_state.setdefault("chat_log", [])
    with st.form("chat_form", clear_on_submit=True):
        question = st.text_input("Question", placeholder="예: 예산을 어떻게 바꾸는 게 좋아?")
        sent = st.form_submit_button("Ask")
    if sent and question:
        try:
            with st.spinner("Thinking..."):
                turn = ask(question, ChatContext(ART, path, ART / "chroma"), st.session_state.get("chat_history"))
            st.session_state["chat_history"] = turn["messages"]
            log.append((question, turn["answer"], [c["name"] for c in turn["tool_calls"]]))
        except Exception as exc:
            st.error(f"Chat failed: {exc}")
    for asked, answer, tools in reversed(log):
        st.markdown(f"**Q. {asked}**")
        if tools:
            st.caption("tools: " + ", ".join(tools))
        st.markdown(answer)

with tab_opt:
    opt_files = sorted(ART.glob("optimum_draws*.json"))
    if not opt_files:
        st.warning("artifacts/optimum_draws.json not found. Run: python -m trend_mmm optimize-draws ...")
    else:
        labels = {
            "optimum_draws_trend_bounded.json": "Trend-aware, bounded (recommended)",
            "optimum_draws_trend.json": "Trend-aware, default bounds",
            "optimum_draws.json": "Base model",
        }
        opt_files.sort(key=lambda p: list(labels).index(p.name) if p.name in labels else len(labels))
        opt = load_json(str(st.selectbox("Result", opt_files, format_func=lambda p: labels.get(p.name, p.name))))
        best, s0, up, each = (opt[k] for k in ("expected_optimum", "s0", "uplift_vs_s0", "per_draw_optimum"))
        lo_pct, hi_pct = opt["interval"]
        level = f"{hi_pct - lo_pct:.0f}%"
        col_a, col_b, col_c = st.columns(3)
        col_a.metric("Expected sales at optimum", f"{best['sales_mean']:,.0f}")
        col_b.metric("Uplift vs S0", f"{up['mean']:,.0f}", f"{100 * up['mean'] / s0['sales_mean']:.1f}%")
        col_c.metric("P(uplift > 0)", f"{up['prob_positive']:.3f}")
        st.write(
            f"{level} interval: sales [{best['sales_interval'][0]:,.0f}, {best['sales_interval'][1]:,.0f}], "
            f"uplift [{up['interval'][0]:,.0f}, {up['interval'][1]:,.0f}] (paired per draw). "
            f"S0 sales {s0['sales_mean']:,.0f}."
        )
        st.vega_lite_chart(shares_chart(opt), width="stretch")
        with st.expander("Table view"):
            st.table(
                [
                    {
                        "channel": ch,
                        "recommended_%": round(100 * share, 1),
                        "per_draw_mean_%": round(100 * each["shares_mean"][ch], 1),
                        f"per_draw_{level}_lo_%": round(100 * each["shares_interval"][ch][0], 1),
                        f"per_draw_{level}_hi_%": round(100 * each["shares_interval"][ch][1], 1),
                        "bounds_%": f"{100 * opt['bounds'][ch][0]:.0f}-{100 * opt['bounds'][ch][1]:.0f}",
                    }
                    for ch, share in best["shares"].items()
                ]
            )
        if best["extrapolation_flags"]:
            st.warning(
                "Extrapolation: "
                + ", ".join(f["channel"] for f in best["extrapolation_flags"])
                + " leaves the historical weekly spend range. Prefer a bounded run."
            )
        st.caption(
            f"Recommended = one allocation maximizing expected sales over {opt['n_draws']} posterior draws. "
            "Per-draw columns show how much the optimum itself moves across draws: wide ranges mean "
            "the exact share is not identified, only the direction."
        )

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
    scen_files = {
        "Trend-aware (adopted)": ART / "scenario_trend_mean.json",
        "Base": ART / "scenario_results.json",
    }
    scen_files = {label: f for label, f in scen_files.items() if f.exists()}
    if not scen_files:
        st.warning("No scenario results in artifacts/. Run: python -m trend_mmm scenarios ...")
    else:
        results = load_json(str(scen_files[st.radio("Model", list(scen_files), horizontal=True)]))
        base = results["S0"]["sales_mean"]
        st.vega_lite_chart(interval_chart(results), width="stretch")
        st.caption(
            "Point = posterior mean, line = 80% credible interval, grey band = S0 interval. "
            "A scenario whose line reaches into the band is not clearly different from S0. "
            "Hollow points left the historical spend range (extrapolated)."
        )
        with st.expander("Table view"):
            st.table(
                [
                    {
                        "scenario": name,
                        "sales_mean": f"{r['sales_mean']:,.0f}",
                        "sales_lo": f"{r['sales_lo']:,.0f}",
                        "sales_hi": f"{r['sales_hi']:,.0f}",
                        "vs_S0_%": round(100 * (r["sales_mean"] / base - 1), 1),
                        "extrapolated": ", ".join(f["channel"] for f in r["extrapolation_flags"]) or "-",
                    }
                    for name, r in results.items()
                ]
            )

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
            if "gamma" in flat and flat["gamma"].shape[1] == len(aux_mean):
                draw["gamma"] = flat["gamma"][i]
            draws.append(draw)
        bundle = {"channels": CHANNELS, "ec50": ec50 or {ch: 1.0 for ch in CHANNELS}}
        if "gamma" in flat and flat["gamma"].shape[1] != len(aux_mean):
            st.warning(
                "This CSV does not have the control/holiday/season columns the model was fitted on, "
                "so those terms are left out. Numbers below are for trying the UI, not for reference."
            )
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

with tab_curve:
    from trend_mmm.mmm.bayesian import adstock_numpy, hill_numpy

    summary_path = ART / "bayes_summary.json"
    if not summary_path.exists():
        st.warning("artifacts/bayes_summary.json not found. Run the bayes CLI first.")
        st.stop()
    summary = load_json(str(summary_path))
    params = summary["posterior"]["params"] if "params" in summary["posterior"] else summary["posterior"]
    ec50 = summary.get("ec50") or {}
    try:
        rows, groups = load_rows(path)
    except Exception as exc:
        st.error(f"Cannot load CSV: {exc}")
        st.stop()
    if not ec50:
        train_rows = rows[: len(rows) - 26]
        ec50 = {
            ch: float(np.median(adstock_numpy(np.array([r["spends"][ch] for r in train_rows]), 0.5)))
            for ch in CHANNELS
        }
    train, _ = rows[: len(rows) - 26], rows[len(rows) - 26 :]
    _, _, train_stats = aux_matrix(train, groups)
    recent = rows[-13:]
    recent_aux, _, _ = aux_matrix(recent, groups, control_stats=train_stats)
    aux_mean = np.asarray(recent_aux, dtype=float).mean(axis=0)
    draw = {"intercept": params["intercept"]["mean"]}
    for ch in CHANNELS:
        draw[f"beta_{ch}"] = params[f"beta_{ch}"]["mean"]
        draw[f"decay_{ch}"] = params[f"decay_{ch}"]["mean"]
        draw[f"alpha_{ch}"] = params[f"alpha_{ch}"]["mean"]
    if "gamma" in params and len(params["gamma"]["mean"]) == len(aux_mean):
        draw["gamma"] = np.array(params["gamma"]["mean"])
    else:
        draw["gamma"] = np.zeros(len(aux_mean))
    total = st.number_input("Total budget (13 weeks)", value=16_200_000, step=100_000, key="curve_total")
    weeks = 13
    base_shares = {"mdsp_sem": 0.5028, "mdsp_dm": 0.2582, "mdsp_so": 0.1321,
                   "mdsp_vidtr": 0.0961, "mdsp_viddig": 0.0108}
    grid = [i / 100 for i in range(0, 61, 3)]
    curves = {}
    for ch in CHANNELS:
        pts = []
        rest = {o: base_shares[o] / (1 - base_shares[ch]) for o in CHANNELS if o != ch}
        for s in grid:
            shares = {o: rest[o] * (1 - s) for o in rest}
            shares[ch] = s
            spends = {c: [total * shares[c] / weeks] * weeks for c in CHANNELS}
            mu = np.full(weeks, draw["intercept"])
            for c in CHANNELS:
                raw = np.maximum(np.asarray(spends[c]), 0.0)
                mu += draw[f"beta_{c}"] * hill_numpy(
                    adstock_numpy(raw, draw[f"decay_{c}"]), draw[f"alpha_{c}"],
                    ec50.get(c, 1.0),
                )
            mu += np.asarray(aux_mean) @ np.asarray(draw["gamma"])
            pts.append(float(mu.sum()))
        curves[ch] = pts
    st.line_chart({ch: vals for ch, vals in curves.items()})
    st.caption(
        "Posterior-mean sales vs channel share (others rescaled, total fixed). "
        "X axis: share 0-60% in 3%p steps. Saturation visible where curves flatten."
    )
