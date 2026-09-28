"""What-if scenario helpers with an extrapolation guard (stdlib only).

Implements docs/scenario.md section 5: fixed total budget, offsetting moves,
non-negative spends, and a flag whenever a scenario spend leaves the
historical observed range.
"""
from trend_mmm.data.validation import SPEND_COLUMNS


def historical_ranges(rows: list[dict], channels: tuple[str, ...] = SPEND_COLUMNS) -> dict:
    """Per-channel (min, max) weekly spend observed in the given rows."""
    return {
        ch: (min(r["spends"][ch] for r in rows), max(r["spends"][ch] for r in rows))
        for ch in channels
    }


def apply_shifts(base_shares: dict, moves: dict) -> dict:
    """Apply budget-point moves (e.g. dm -0.05, vidtr +0.05).

    Moves must sum to ~0 and no share may go negative or exceed 1.
    """
    if abs(sum(moves.values())) > 1e-9:
        raise ValueError(f"Moves must sum to 0, got {sum(moves.values())}.")
    shares = dict(base_shares)
    for channel, delta in moves.items():
        if channel not in shares:
            raise ValueError(f"Unknown channel: {channel}.")
        shares[channel] += delta
    for channel, share in shares.items():
        if not 0.0 <= share <= 1.0:
            raise ValueError(f"Share out of [0, 1] for {channel}: {share}.")
    return shares


def scenario_spends(total: float, shares: dict, weeks: int) -> dict:
    """Uniform weekly allocation of the total budget by share."""
    if total < 0:
        raise ValueError("Total budget must be non-negative.")
    if weeks < 1:
        raise ValueError("Weeks must be >= 1.")
    return {ch: [total * share / weeks] * weeks for ch, share in shares.items()}


def check_extrapolation(scenario: dict, ranges: dict) -> list[dict]:
    """Flag channels whose scenario spend leaves the historical range."""
    flags = []
    for channel, values in scenario.items():
        lo, hi = ranges[channel]
        outside = [v for v in values if v < lo or v > hi]
        if outside:
            flags.append(
                {
                    "channel": channel,
                    "n_outside": len(outside),
                    "min_value": min(values),
                    "max_value": max(values),
                    "hist_min": lo,
                    "hist_max": hi,
                }
            )
    return flags
