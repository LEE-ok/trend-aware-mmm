import unittest

import numpy as np

from trend_mmm.data.validation import SPEND_COLUMNS
from trend_mmm.optimization.allocate import (
    _params,
    channel_sales,
    optimize,
    optimize_draws,
    response_mean,
)

CHS = list(SPEND_COLUMNS)
BUNDLE = {"channels": CHS, "ec50": {ch: 100.0 for ch in CHS}}
BOUNDS = {ch: (0.0, 0.6) for ch in CHS}
TOTAL, WEEKS = 4000.0, 4


def make_draws(n=8, seed=0):
    rng = np.random.default_rng(seed)
    return [
        {"intercept": 1000.0,
         **{f"beta_{ch}": float(rng.uniform(5, 50)) for ch in CHS},
         **{f"decay_{ch}": float(rng.uniform(0.0, 0.6)) for ch in CHS},
         **{f"alpha_{ch}": float(rng.uniform(0.4, 1.0)) for ch in CHS}}
        for _ in range(n)
    ]


class OptimizeDrawsTests(unittest.TestCase):
    def test_channel_sales_matches_loop_reference(self):
        draws = make_draws()
        shares = {ch: s for ch, s in zip(CHS, (0.0, 0.1, 0.2, 0.3, 0.4))}
        spends = {ch: [TOTAL * shares[ch] / WEEKS] * WEEKS for ch in CHS}
        fast = channel_sales(_params(draws, BUNDLE), list(shares.values()), TOTAL, WEEKS).sum(axis=1)
        slow = [response_mean(d, BUNDLE, spends, None).sum() - d["intercept"] * WEEKS for d in draws]
        np.testing.assert_allclose(fast, slow, rtol=1e-9)

    def test_shares_keep_total_and_bounds(self):
        bounds = {**BOUNDS, CHS[0]: (0.05, 0.6)}
        shares, _ = optimize_draws(make_draws(), BUNDLE, TOTAL, WEEKS, bounds)
        np.testing.assert_allclose(shares.sum(axis=1), 1.0)
        self.assertTrue((shares[:, 0] >= 0.05 - 1e-9).all())
        self.assertTrue((shares <= 0.6 + 1e-9).all())

    def test_single_draw_agrees_with_point_optimizer(self):
        draw = make_draws(1, seed=3)[0]
        shares, _ = optimize_draws([draw], BUNDLE, TOTAL, WEEKS, BOUNDS)
        point = optimize(draw, BUNDLE, TOTAL, WEEKS, None, BOUNDS)
        fast = float(channel_sales(_params([draw], BUNDLE), shares, TOTAL, WEEKS).sum())
        self.assertGreaterEqual(fast + draw["intercept"] * WEEKS, point["sales"] - 1e-6)
        for i, ch in enumerate(CHS):
            self.assertAlmostEqual(shares[0, i], point["shares"][ch], delta=0.03)

    def test_pooled_beats_equal_split_and_per_draw_beats_pooled(self):
        draws = make_draws()
        params = _params(draws, BUNDLE)
        pooled, _ = optimize_draws(draws, BUNDLE, TOTAL, WEEKS, BOUNDS, pooled=True)
        each, _ = optimize_draws(draws, BUNDLE, TOTAL, WEEKS, BOUNDS)
        self.assertEqual(pooled.shape, (1, len(CHS)))
        equal = channel_sales(params, np.full(len(CHS), 0.2), TOTAL, WEEKS).sum(axis=1)
        at_pooled = channel_sales(params, pooled, TOTAL, WEEKS).sum(axis=1)
        at_each = channel_sales(params, each, TOTAL, WEEKS).sum(axis=1)
        self.assertGreater(at_pooled.mean(), equal.mean())
        self.assertTrue((at_each >= at_pooled - 1e-6).all())

    def test_tight_cap_below_equal_split_is_respected(self):
        shares, _ = optimize_draws(make_draws(), BUNDLE, TOTAL, WEEKS, {**BOUNDS, CHS[3]: (0.0, 0.08)})
        np.testing.assert_allclose(shares.sum(axis=1), 1.0)
        self.assertTrue((shares[:, 3] <= 0.08 + 1e-9).all())

    def test_infeasible_bounds_rejected(self):
        with self.assertRaises(ValueError):
            optimize_draws(make_draws(2), BUNDLE, TOTAL, WEEKS, {ch: (0.0, 0.1) for ch in CHS})


if __name__ == "__main__":
    unittest.main()
