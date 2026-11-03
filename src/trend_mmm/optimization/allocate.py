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


def _params(draws, bundle):
    """Stack per-draw channel parameters into (D, C) arrays."""
    channels = tuple(bundle["channels"])

    def stack(prefix):
        return np.array([[d[f"{prefix}_{ch}"] for ch in channels] for d in draws], dtype=float)

    ec50 = np.array([bundle["ec50"][ch] for ch in channels], dtype=float)
    return stack("beta"), stack("decay"), stack("alpha"), ec50


def channel_sales(params, shares, total: float, weeks: int) -> np.ndarray:
    """Per-draw channel contribution (D, C) under uniform weekly spend.

    Constant spend x from zero carryover gives adstock_t = x * (1 - decay^t) / (1 - decay),
    so every draw is evaluated at once (same numbers as adstock_numpy + hill_numpy).
    """
    beta, decay, alpha, ec50 = params
    t = np.arange(1, weeks + 1)
    geom = (1.0 - decay[..., None] ** t) / (1.0 - decay[..., None])
    stock = np.maximum(total * np.asarray(shares, dtype=float)[..., None] / weeks, 0.0) * geom
    num = stock ** alpha[..., None]
    return beta * (num / (num + ec50[:, None] ** alpha[..., None])).sum(axis=-1)


def optimize_draws(
    draws,
    bundle,
    total: float,
    weeks: int,
    bounds: dict,
    pooled: bool = False,
    step: float = 0.001,
    max_iters: int = 5000,
    objective: str = "mean",
    q: float = 0.1,
    offset=None,
):
    """Greedy step reallocation over posterior draws. Returns (shares, iters).

    pooled=False: one optimum per draw, shares (D, C) -> how uncertain the optimum is.
    pooled=True: one allocation maximizing expected sales over all draws, shares (1, C)
    -> the recommendation, which can then be scored on every draw for an interval.
    Each iteration takes the single donor->receiver step that raises the objective
    most and stops when no step helps. Intercept and aux do not depend on shares,
    so they are left out of the objective.
    objective='quantile' (pooled only): maximize the q-quantile of total sales over draws
    instead of the mean (downside-risk view). Which draws sit in the low tail depends on
    intercept + aux, so pass offset (D,) = per-draw non-channel sales (draw_offsets).
    """
    # ponytail: local search from one start point; Hill with alpha > 1 is S-shaped, so
    # this is a local optimum. random_check (CLI check-optimum) tests it against random splits.
    channels = tuple(bundle["channels"])
    n = len(channels)
    lo = np.array([bounds[ch][0] for ch in channels], dtype=float)
    hi = np.array([bounds[ch][1] for ch in channels], dtype=float)
    if (lo > hi).any() or lo.sum() > 1.0 or hi.sum() < 1.0:
        raise ValueError("Bounds are infeasible: need lo <= hi and sum(lo) <= 1 <= sum(hi).")
    # Feasible start: lower bounds plus headroom-proportional remainder (equal split by default).
    start = lo + (1.0 - lo.sum()) * (hi - lo) / (hi - lo).sum()
    if objective not in ("mean", "quantile"):
        raise ValueError("objective must be 'mean' or 'quantile'.")
    if objective == "quantile" and not 0.0 < q < 1.0:
        raise ValueError("q must be in (0, 1).")
    params = _params(draws, bundle)
    if objective == "quantile" and pooled:
        return _optimize_quantile(params, total, weeks, lo, hi, start, step, max_iters, q, offset)
    rows = 1 if pooled else len(draws)
    shares = np.tile(start, (rows, 1))

    def value(sh):
        v = channel_sales(params, sh, total, weeks)
        return v.mean(axis=0, keepdims=True) if pooled else v

    eye = np.eye(n, dtype=bool)
    pick = np.arange(rows)
    iters = 0
    for iters in range(max_iters):
        base = value(shares)
        up = np.where(shares + step <= hi + 1e-12, value(shares + step) - base, -np.inf)
        down = np.where(shares - step >= lo - 1e-12, base - value(shares - step), np.inf)
        net = up[:, :, None] - down[:, None, :]  # [row, receiver, donor]
        net[:, eye] = -np.inf
        flat = net.reshape(rows, -1)
        best = flat.argmax(axis=1)
        move = np.flatnonzero(flat[pick, best] > 1e-9 * base.sum(axis=1))
        if move.size == 0:
            break
        receiver, donor = np.divmod(best, n)
        shares[move, receiver[move]] += step
        shares[move, donor[move]] -= step
    return np.clip(shares, lo, hi), iters


def _optimize_quantile(params, total, weeks, lo, hi, start, step, max_iters, q, offset):
    """Same greedy search as optimize_draws, objective = q-quantile of per-draw total sales.

    A quantile is not additive over channels, so every (receiver, donor) move is scored on
    per-draw totals (D, C, C) before taking the quantile over draws.
    """
    n = len(lo)
    offset = np.zeros(len(params[0])) if offset is None else np.asarray(offset, dtype=float)
    shares = start[None, :].copy()
    eye = np.eye(n, dtype=bool)
    iters = 0
    for iters in range(max_iters):
        cur = channel_sales(params, shares, total, weeks)  # (D, C)
        tot = offset + cur.sum(axis=1)
        up = channel_sales(params, shares + step, total, weeks) - cur
        down = cur - channel_sales(params, shares - step, total, weeks)
        cand = tot[:, None, None] + up[:, :, None] - down[:, None, :]  # [draw, receiver, donor]
        base = np.quantile(tot, q)
        net = np.quantile(cand, q, axis=0) - base
        net[~(shares[0] + step <= hi + 1e-12), :] = -np.inf
        net[:, ~(shares[0] - step >= lo - 1e-12)] = -np.inf
        net[eye] = -np.inf
        receiver, donor = np.unravel_index(net.argmax(), net.shape)
        if net[receiver, donor] <= 1e-9 * abs(base):
            break
        shares[0, receiver] += step
        shares[0, donor] -= step
    return np.clip(shares, lo, hi), iters


def draw_offsets(draws, weeks: int, aux_mean) -> np.ndarray:
    """Per-draw sales that do not depend on the split: intercept + aux over the horizon."""
    out = np.array([d["intercept"] for d in draws], dtype=float)
    if aux_mean is not None and draws and "gamma" in draws[0]:
        out = out + np.array([np.asarray(aux_mean, dtype=float) @ np.asarray(d["gamma"]) for d in draws])
    return weeks * out


def objective_value(params, shares, total: float, weeks: int, objective="mean", q=0.1, offset=None) -> float:
    """Pooled objective of one split: mean or q-quantile of per-draw sales (channel part + offset)."""
    sales = channel_sales(params, shares, total, weeks).sum(axis=-1)
    if offset is not None:
        sales = sales + np.asarray(offset, dtype=float)
    return float(sales.mean() if objective == "mean" else np.quantile(sales, q))


def random_check(
    draws, bundle, total: float, weeks: int, bounds: dict, shares,
    n: int = 3000, seed: int = 0, objective: str = "mean", q: float = 0.1, offset=None,
) -> dict:
    """Local-optimum check: score n random feasible splits against `shares` on the same objective.

    Splits are lo + (1 - sum(lo)) * Dirichlet(1), rejected when above hi, so they cover the
    whole bounded simplex. With S-shaped Hill (alpha > 1) a greedy result can be local;
    n_better > 0 means a better split exists.
    """
    channels = tuple(bundle["channels"])
    lo = np.array([bounds[ch][0] for ch in channels], dtype=float)
    hi = np.array([bounds[ch][1] for ch in channels], dtype=float)
    params = _params(draws, bundle)
    rng = np.random.default_rng(seed)
    samples, tries = [], 0
    while sum(len(s) for s in samples) < n:
        tries += 1
        if tries > 1000:
            raise ValueError("Bounds too tight for rejection sampling of random splits.")
        cand = lo + (1.0 - lo.sum()) * rng.dirichlet(np.ones(len(channels)), size=n)
        samples.append(cand[(cand <= hi + 1e-12).all(axis=1)])
    samples = np.concatenate(samples)[:n]
    best = objective_value(params, np.asarray(shares, dtype=float).reshape(-1), total, weeks, objective, q, offset)
    values = np.array([objective_value(params, s, total, weeks, objective, q, offset) for s in samples])
    top = int(values.argmax())
    return {
        "n": n,
        "seed": seed,
        "objective_at_optimum": best,
        "n_better": int((values > best + 1e-9 * abs(best)).sum()),
        "max_improvement": float(values[top] - best),
        "max_improvement_pct": float(100 * (values[top] / best - 1)) if best else 0.0,
        "best_random_shares": dict(zip(channels, (float(v) for v in samples[top]))),
    }
