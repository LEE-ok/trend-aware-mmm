"""Budget optimization under channel bounds (stdlib + numpy).

Greedy marginal reallocation on the posterior-mean response surface:
move budget from the lowest-marginal-ROAS channel to the highest until
marginals equalize or bounds bind. Valid for concave (diminishing-return)
response, which the Hill saturation guarantees.
"""
import numpy as np

from trend_mmm.mmm.bayesian import adstock_numpy, hill_numpy


def response_mean(draw, bundle, spends, aux_mean):
    """Posterior-mean weekly sales for a spend plan."""
    channels = tuple(bundle["channels"])
    ec50 = bundle["ec50"]
    weeks = len(next(iter(spends.values())))
    mu = np.full(weeks, draw["intercept"], dtype=float)
    for ch in channels:
        raw = np.maximum(np.asarray(spends[ch], dtype=float), 0.0)
        mu += draw[f"beta_{ch}"] * hill_numpy(
            adstock_numpy(raw, draw[f"decay_{ch}"]), draw[f"alpha_{ch}"], ec50[ch]
        )
    if aux_mean is not None and "gamma" in draw:
        mu += np.asarray(aux_mean, dtype=float) @ np.asarray(draw["gamma"])
    return mu


def marginal_gains(draw, bundle, spends, aux_mean):
    """Extra sales per extra spend unit, per channel (+1% bump)."""
    base = response_mean(draw, bundle, spends, aux_mean).sum()
    gains = {}
    for ch, vals in spends.items():
        up = dict(spends)
        up[ch] = [v * 1.01 for v in vals]
        d_spend = sum(up[ch]) - sum(vals)
        d_sales = response_mean(draw, bundle, up, aux_mean).sum() - base
        gains[ch] = d_sales / d_spend if d_spend else 0.0
    return gains


def optimize(
    draw,
    bundle,
    total: float,
    weeks: int,
    aux_mean,
    bounds: dict,
    step: float = 0.001,
    max_iters: int = 5000,
    tol: float = 0.02,
) -> dict:
    """Return {shares, sales, marginal_roas, iters}. Total is preserved.

    Stops when the best movable gain exceeds the worst by less than
    tol (relative, default 2%: economic convergence). Bounds are
    clipped at the end.
    """
    channels = tuple(bundle["channels"])
    n = len(channels)
    shares = {ch: 1.0 / n for ch in channels}
    lo = {ch: bounds[ch][0] for ch in channels}
    hi = {ch: bounds[ch][1] for ch in channels}

    def spends(sh):
        return {ch: [total * sh[ch] / weeks] * weeks for ch in channels}

    iters = 0
    for iters in range(1, max_iters + 1):
        gains = marginal_gains(draw, bundle, spends(shares), aux_mean)
        donors = [ch for ch in channels if shares[ch] - step >= lo[ch] - 1e-12]
        receivers = [ch for ch in channels if shares[ch] + step <= hi[ch] + 1e-12]
        if not donors or not receivers:
            break
        donor = min(donors, key=lambda c: gains[c])
        receiver = max(receivers, key=lambda c: gains[c])
        scale = max(abs(gains[c]) for c in channels) or 1.0
        if donor == receiver or (gains[receiver] - gains[donor]) <= tol * scale:
            break
        shares[donor] -= step
        shares[receiver] += step
    else:
        iters = max_iters
    shares = {ch: min(max(shares[ch], lo[ch]), hi[ch]) for ch in channels}
    total_share = sum(shares.values())
    shares = {ch: s / total_share for ch, s in shares.items()}
    final_spends = spends(shares)
    return {
        "shares": shares,
        "sales": float(response_mean(draw, bundle, final_spends, aux_mean).sum()),
        "marginal_roas": marginal_gains(draw, bundle, final_spends, aux_mean),
        "iters": iters,
    }
