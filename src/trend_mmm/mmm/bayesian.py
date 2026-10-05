"""Bayesian MMM, priors v1.0 (docs/priors.md). Requires pymc.

Structure: per-channel geometric adstock (estimated decay) + Hill
saturation (estimated alpha, ec50 fixed at train median) + HalfNormal
channel coefficients (non-negative by construction) + standardized
controls + bundled holidays + seas_prd_* period dummies (first dropped).
"""
import numpy as np

CHANNEL_PRIORS = {
    "mdsp_dm": {"beta_sd": 5e7, "decay": (0.3, 0.7)},
    "mdsp_so": {"beta_sd": 5e7, "decay": (0.0, 0.4)},
    "mdsp_vidtr": {"beta_sd": 1.5e8, "decay": (0.3, 0.7)},
    "mdsp_viddig": {"beta_sd": 5e7, "decay": (0.0, 0.4)},
    "mdsp_sem": {"beta_sd": 1.5e8, "decay": (0.0, 0.5)},
}
ALPHA_RANGE = (0.3, 1.5)
INTERCEPT_SD = 3e7
SIGMA_SD = 4e7
AUX_SD = 1e7


def adstock_numpy(series: np.ndarray, decay: float) -> np.ndarray:
    """Reference carryover (also used for posterior-mean transforms)."""
    out = np.empty_like(series, dtype=float)
    carry = 0.0
    for i, value in enumerate(series):
        carry = value + decay * carry
        out[i] = carry
    return out


def hill_numpy(series: np.ndarray, alpha: float, ec50: float) -> np.ndarray:
    num = np.power(np.asarray(series, dtype=float), alpha)
    return np.where(np.asarray(series) > 0, num / (num + ec50**alpha), 0.0)


def build_features(rows: list[dict], channels: tuple[str, ...]) -> dict:
    """Raw spend matrix + fixed ec50 (train median of adstock at decay 0.5)."""
    return {
        "spends": {ch: np.array([r["spends"][ch] for r in rows], dtype=float) for ch in channels},
        "sales": np.array([r["sales"] for r in rows], dtype=float),
    }


def fit_bayesian(
    train: list[dict],
    channels: tuple[str, ...],
    aux: np.ndarray | None = None,
    draws: int = 500,
    tune: int = 500,
    chains: int = 2,
    seed: int = 7,
):
    """Sample the posterior. Returns (idata, feature_bundle)."""
    import pymc as pm
    import pytensor.tensor as pt
    from pytensor.scan import scan

    n = len(train)
    feats = build_features(train, channels)
    sales = feats["sales"]
    ec50 = {}
    for ch in channels:
        med = float(np.median(adstock_numpy(feats["spends"][ch], 0.5)))
        ec50[ch] = med if med > 0 else 1.0

    with pm.Model() as model:
        intercept = pm.Normal("intercept", mu=float(sales.mean()), sigma=INTERCEPT_SD)
        sigma = pm.HalfNormal("sigma", sigma=SIGMA_SD)
        mu = pt.as_tensor_variable(np.full(n, 0.0)) + intercept
        for ch in channels:
            prior = CHANNEL_PRIORS[ch]
            decay = pm.Uniform(f"decay_{ch}", *prior["decay"])
            alpha = pm.Uniform(f"alpha_{ch}", *ALPHA_RANGE)
            beta = pm.HalfNormal(f"beta_{ch}", sigma=prior["beta_sd"])
            spend = pt.as_tensor_variable(feats["spends"][ch])

            def step(x_t, carry, d):
                return x_t + d * carry

            stocked = scan(
                fn=step,
                sequences=[spend],
                outputs_info=[pt.zeros(())],
                non_sequences=[decay],
                return_updates=False,
            )
            sat = pt.switch(
                stocked > 0,
                pt.power(stocked, alpha) / (pt.power(stocked, alpha) + ec50[ch] ** alpha),
                0.0,
            )
            mu = mu + beta * sat
        if aux is not None and aux.shape[1] > 0:
            gamma = pm.Normal("gamma", mu=0.0, sigma=AUX_SD, shape=aux.shape[1])
            mu = mu + pt.dot(np.asarray(aux, dtype=float), gamma)
        pm.Normal("obs", mu=mu, sigma=sigma, observed=sales)
        idata = pm.sample(
            draws=draws, tune=tune, chains=chains, target_accept=0.95,
            random_seed=seed, progressbar=False,
        )
    return idata, {"ec50": ec50, "channels": list(channels)}


def posterior_mean(idata, name: str) -> float:
    vals = idata.posterior[name].values
    return float(vals.mean())


def predict_posterior_mean(
    idata, bundle: dict, rows: list[dict], aux: np.ndarray | None = None
) -> np.ndarray:
    """Posterior-mean prediction. History restarts at the given rows."""
    channels = bundle["channels"]
    draws = idata.posterior
    mus = np.zeros(len(rows))
    for ch in channels:
        decay = float(draws[f"decay_{ch}"].values.mean())
        alpha = float(draws[f"alpha_{ch}"].values.mean())
        beta = float(draws[f"beta_{ch}"].values.mean())
        raw = np.array([r["spends"][ch] for r in rows], dtype=float)
        mus += beta * hill_numpy(adstock_numpy(raw, decay), alpha, bundle["ec50"][ch])
    mus += posterior_mean(idata, "intercept")
    if aux is not None and "gamma" in draws:
        mus += np.asarray(aux, dtype=float) @ np.asarray(draws["gamma"].values.mean(axis=(0, 1)))
    return mus


def summarize_posterior(idata, channels: tuple[str, ...]) -> dict:
    """Means, sds and max R-hat for the report."""
    import arviz as az

    out: dict = {"params": {}}
    for ch in channels:
        for prefix in ("beta", "decay", "alpha"):
            name = f"{prefix}_{ch}"
            vals = idata.posterior[name].values
            out["params"][name] = {"mean": float(vals.mean()), "sd": float(vals.std())}
    for name in ("intercept", "sigma"):
        vals = idata.posterior[name].values
        out["params"][name] = {"mean": float(vals.mean()), "sd": float(vals.std())}
    if "gamma" in idata.posterior:
        vals = idata.posterior["gamma"].values
        out["params"]["gamma"] = {
            "mean": [float(v) for v in vals.mean(axis=(0, 1))],
            "sd": [float(v) for v in vals.std(axis=(0, 1))],
        }
    rhat = az.rhat(idata)
    out["max_rhat"] = max(float(v.values.max()) for v in rhat.values())
    return out
