import unittest

import numpy as np

from trend_mmm.data.validation import SPEND_COLUMNS
from trend_mmm.optimization.allocate import marginal_gains, optimize, response_mean

CHS = list(SPEND_COLUMNS)
EC50 = {ch: 100.0 for ch in CHS}
BUNDLE = {"channels": CHS, "ec50": EC50}
DRAW = {"intercept": 1000.0, **{f"beta_{ch}": 10.0 for ch in CHS},
        **{f"decay_{ch}": 0.3 for ch in CHS}, **{f"alpha_{ch}": 1.0 for ch in CHS}}
BOUNDS = {ch: (0.0, 0.6) for ch in CHS}


def spends(shares, weeks=4, total=4000.0):
    return {ch: [total * shares[ch] / weeks] * weeks for ch in CHS}


class AllocateTests(unittest.TestCase):
    def test_response_scales_with_spend(self):
        base = response_mean(DRAW, BUNDLE, spends({ch: 0.2 for ch in CHS}), None)
        up = response_mean(DRAW, BUNDLE, spends({**{ch: 0.2 for ch in CHS}, CHS[0]: 0.4}), None)
        self.assertGreater(up.sum(), base.sum())

    def test_marginals_diminish(self):
        low = spends({ch: 0.2 for ch in CHS})
        high = spends({**{ch: 0.2 for ch in CHS}, CHS[0]: 0.5})
        self.assertGreater(
            marginal_gains(DRAW, BUNDLE, low, None)[CHS[0]],
            marginal_gains(DRAW, BUNDLE, high, None)[CHS[0]],
        )

    def test_optimize_preserves_total_and_bounds(self):
        res = optimize(DRAW, BUNDLE, 4000.0, 4, None, BOUNDS)
        self.assertAlmostEqual(sum(res["shares"].values()), 1.0)
        for ch, (lo, hi) in BOUNDS.items():
            self.assertGreaterEqual(res["shares"][ch], lo - 1e-9)
            self.assertLessEqual(res["shares"][ch], hi + 1e-9)

    def test_optimize_beats_equal_split(self):
        equal = sum(response_mean(DRAW, BUNDLE, spends({ch: 0.2 for ch in CHS}), None))
        res = optimize(DRAW, BUNDLE, 4000.0, 4, None, BOUNDS)
        self.assertGreaterEqual(res["sales"], equal)

    def test_marginals_equalize_within_bounds(self):
        res = optimize(DRAW, BUNDLE, 4000.0, 4, None, BOUNDS)
        g = res["marginal_roas"]
        free = [ch for ch in CHS if 0.0 < res["shares"][ch] < 0.6]
        if len(free) >= 2:
            vals = [g[ch] for ch in free]
            self.assertLess(max(vals) - min(vals), 1.0)


if __name__ == "__main__":
    unittest.main()
