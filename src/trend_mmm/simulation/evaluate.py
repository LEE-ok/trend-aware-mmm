"""Posterior scenario evaluation S0-S4 (docs/scenario.md). numpy only.

Fixed total budget, offsetting moves, uniform weekly allocation.
Aux (controls/holidays/season) is held at the recent-13w mean for every
scenario (scenario.md section 5.4), so differences come from spends only.
Uncertainty: 80% credible interval (configs/project.toml).
"""
import numpy as np

from trend_mmm.mmm.bayesian import adstock_numpy, hill_numpy
from trend_mmm.simulation.scenarios import (
    apply_shifts,
    check_extrapolation,
    historical_ranges,
    scenario_spends,
)

BASE_SHARES = {
    "mdsp_sem": 0.5028,
    "mdsp_dm": 0.2582,
    "mdsp_so": 0.1321,
    "mdsp_vidtr": 0.0961,
    "mdsp_viddig": 0.0108,
}
MOVES = {
    "S1": ("mdsp_dm", "mdsp_vidtr"),
    "S2": ("mdsp_dm", "mdsp_sem"),
    "S3": ("mdsp_dm", "mdsp_viddig"),
    "S4": ("mdsp_dm", "mdsp_so"),
}
SHIFTS = (0.05, 0.10, 0.15)
INTERVAL_LO, INTERVAL_HI = 10.0, 90.0


def scenario_defs() -> dict:
    """All scenario variants: S0 + S{1..4}_{05,10,15} with share dicts."""
    defs = {"S0": dict(BASE_SHARES)}
    for name, (src, dst) in MOVES.items():
        for pct in SHIFTS:
            moves = {src: -pct, dst: pct}
            defs[f"{name}_{int(pct * 100):02d}"] = apply_shifts(BASE_SHARES, moves)
    return defs


def _weekly_mu(draw: dict, spends: dict, channels: tuple, ec50: dict, aux_mean):
    """Posterior-mean weekly sales for one draw."""
    weeks = len(next(iter(spends.values())))
    mu = np.full(weeks, draw["intercept"])
    for ch in channels:
        sat = hill_numpy(
            adstock_numpy(np.asarray(spends[ch], dtype=float), draw[f"decay_{ch}"]),
            draw[f"alpha_{ch}"],
            ec50[ch],
        )
        mu += draw[f"beta_{ch}"] * sat
    if aux_mean is not None and "gamma" in draw:
        mu += np.asarray(aux_mean, dtype=float) @ np.asarray(draw["gamma"])
    return mu


def evaluate(
    draws: list[dict],
    bundle: dict,
    total: float,
    shares: dict,
    weeks: int,
    aux_mean,
    ranges: dict,
) -> dict:
    """Posterior distribution over total sales + channel economics."""
    channels = tuple(bundle["channels"])
    ec50 = bundle["ec50"]
    spends = scenario_spends(total, shares, weeks)
    totals = np.array([_weekly_mu(d, spends, channels, ec50, aux_mean).sum() for d in draws])
    contrib = {}
    for ch in channels:
        raw = np.asarray(spends[ch], dtype=float)
        vals = np.array(
            [
                (
                    d[f"beta_{ch}"]
                    * hill_numpy(adstock_numpy(raw, d[f"decay_{ch}"]), d[f"alpha_{ch}"], ec50[ch])
                ).sum()
                for d in draws
            ]
        )
        contrib[ch] = vals
    spend_totals = {ch: total * shares[ch] for ch in channels}
    roas = {
        ch: float(contrib[ch].mean() / spend_totals[ch]) if spend_totals[ch] > 0 else 0.0
        for ch in channels
    }
    flags = check_extrapolation(spends, ranges)
    return {
        "shares": dict(shares),
        "total_spend": total,
        "weeks": weeks,
        "sales_mean": float(totals.mean()),
        "sales_lo": float(np.percentile(totals, INTERVAL_LO)),
        "sales_hi": float(np.percentile(totals, INTERVAL_HI)),
        "contrib_mean": {ch: float(contrib[ch].mean()) for ch in channels},
        "roas": roas,
        "extrapolation_flags": flags,
    }


def marginal_roas(
    draws: list[dict], bundle: dict, total: float, shares: dict,
    weeks: int, aux_mean, channel: str, bump: float = 0.01,
) -> float:
    """dSales/dSpend for one channel via a +1% spend bump (others fixed)."""
    channels = tuple(bundle["channels"])
    ec50 = bundle["ec50"]
    base_spends = scenario_spends(total, shares, weeks)
    up_spends = dict(base_spends)
    up_spends[channel] = [v * (1 + bump) for v in base_spends[channel]]
    d_spend = sum(up_spends[channel]) - sum(base_spends[channel])
    d_sales = np.mean(
        [
            _weekly_mu(d, up_spends, channels, ec50, aux_mean).sum()
            - _weekly_mu(d, base_spends, channels, ec50, aux_mean).sum()
            for d in draws
        ]
    )
    return float(d_sales / d_spend) if d_spend else 0.0
