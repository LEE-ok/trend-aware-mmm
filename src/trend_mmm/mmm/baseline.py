"""Baseline MMM: global adstock + Hill saturation + OLS (stdlib only).

Not Bayesian. This is the reference point the Bayesian MMM and the
trend-aware variant must beat on the same time-ordered test window.
Priors live in docs/priors.md; this module takes no prior input.
"""
import math

DECAY_GRID = (0.0, 0.3, 0.5, 0.7)
ALPHA_GRID = (0.5, 0.7, 1.0)


def adstock(series: list[float], decay: float) -> list[float]:
    """Carryover: out[t] = x[t] + decay * out[t-1]."""
    out: list[float] = []
    carry = 0.0
    for value in series:
        carry = value + decay * carry
        out.append(carry)
    return out


def saturate(series: list[float], alpha: float, ec50: float) -> list[float]:
    """Hill saturation in [0, 1). alpha=1 gives x / (x + ec50)."""
    if ec50 <= 0:
        raise ValueError("ec50 must be positive")
    return [(v**alpha) / (v**alpha + ec50**alpha) if v > 0 else 0.0 for v in series]


def _median(values: list[float]) -> float:
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[mid]
    return (ordered[mid - 1] + ordered[mid]) / 2


def _solve(matrix: list[list[float]], vector: list[float]) -> list[float]:
    """Gauss-Jordan solve for small systems. Raises on singular matrix."""
    n = len(vector)
    aug = [row[:] + [vector[i]] for i, row in enumerate(matrix)]
    for col in range(n):
        pivot = max(range(col, n), key=lambda r: abs(aug[r][col]))
        if abs(aug[pivot][col]) < 1e-12:
            raise ValueError("Singular matrix in OLS.")
        aug[col], aug[pivot] = aug[pivot], aug[col]
        scale = aug[col][col]
        aug[col] = [v / scale for v in aug[col]]
        for r in range(n):
            if r != col and aug[r][col] != 0.0:
                factor = aug[r][col]
                aug[r] = [a - factor * b for a, b in zip(aug[r], aug[col])]
    return [aug[i][n] for i in range(n)]


def fit_ols(features: list[list[float]], target: list[float]) -> list[float]:
    """OLS with intercept. Returns [intercept, b1, ...]."""
    design = [[1.0, *row] for row in features]
    n, p = len(design), len(design[0])
    xtx = [[sum(design[i][a] * design[i][b] for i in range(n)) for b in range(p)] for a in range(p)]
    xty = [sum(design[i][a] * target[i] for i in range(n)) for a in range(p)]
    return _solve(xtx, xty)


def _transform(
    rows: list[dict], channels: tuple[str, ...], decay: float, alpha: float, ec50: dict[str, float]
) -> list[list[float]]:
    """Adstock over the full history, then saturate. Returns feature rows."""
    raw = {ch: [r["spends"][ch] for r in rows] for ch in channels}
    stocked = {ch: adstock(raw[ch], decay) for ch in channels}
    return [
        [saturate([stocked[ch][i]], alpha, ec50[ch])[0] for ch in channels]
        for i in range(len(rows))
    ]


def fit_baseline(
    train: list[dict],
    channels: tuple[str, ...],
    decays: tuple[float, ...] = DECAY_GRID,
    alphas: tuple[float, ...] = ALPHA_GRID,
) -> dict:
    """Grid-search (decay, alpha) on train MAPE. ec50 = train median per channel."""
    target = [r["sales"] for r in train]
    best: dict | None = None
    for decay in decays:
        stocked = {ch: adstock([r["spends"][ch] for r in train], decay) for ch in channels}
        ec50 = {ch: _median(stocked[ch]) or 1.0 for ch in channels}
        for alpha in alphas:
            feats = _transform(train, channels, decay, alpha, ec50)
            try:
                coefs = fit_ols(feats, target)
            except ValueError:
                continue
            preds = [coefs[0] + sum(b * x for b, x in zip(coefs[1:], row)) for row in feats]
            err = metrics(target, preds)["mape"]
            if best is None or err < best["train_mape"]:
                best = {
                    "decay": decay,
                    "alpha": alpha,
                    "ec50": ec50,
                    "intercept": coefs[0],
                    "coefs": dict(zip(channels, coefs[1:])),
                    "train_mape": err,
                    "train_weeks": len(train),
                }
    if best is None:
        raise ValueError("No (decay, alpha) combination produced a fit.")
    return best


def predict(model: dict, rows: list[dict], channels: tuple[str, ...]) -> list[float]:
    """Apply a fitted baseline model. History starts at the given rows."""
    feats = _transform(rows, channels, model["decay"], model["alpha"], model["ec50"])
    coefs = [model["coefs"][ch] for ch in channels]
    return [model["intercept"] + sum(b * x for b, x in zip(coefs, row)) for row in feats]


def metrics(actual: list[float], predicted: list[float]) -> dict:
    """MAPE, RMSE, MAE and directional accuracy (week-over-week)."""
    n = len(actual)
    ape = [abs((a - p) / a) if a != 0 else 0.0 for a, p in zip(actual, predicted)]
    se = [(a - p) ** 2 for a, p in zip(actual, predicted)]
    hits = sum(
        1
        for i in range(1, n)
        if (actual[i] - actual[i - 1]) * (predicted[i] - predicted[i - 1]) > 0
    )
    return {
        "mape": sum(ape) / n,
        "rmse": math.sqrt(sum(se) / n),
        "mae": sum(abs(a - p) for a, p in zip(actual, predicted)) / n,
        "dir_acc": hits / (n - 1) if n > 1 else 0.0,
    }
