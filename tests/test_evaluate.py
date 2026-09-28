import unittest

import numpy as np

from trend_mmm.data.validation import SPEND_COLUMNS
from trend_mmm.simulation.evaluate import evaluate, marginal_roas, scenario_defs

EC50 = {ch: 100.0 for ch in SPEND_COLUMNS}
BUNDLE = {"channels": list(SPEND_COLUMNS), "ec50": EC50}


def fake_draws(n=8):
    draws = []
    for i in range(n):
        draw = {"intercept": 1000.0 + i}
        for ch in SPEND_COLUMNS:
            draw[f"beta_{ch}"] = 10.0
            draw[f"decay_{ch}"] = 0.3
            draw[f"alpha_{ch}"] = 1.0
        draws.append(draw)
    return draws


class EvaluateTests(unittest.TestCase):
    def test_defs_cover_s0_s4(self):
        defs = scenario_defs()
        self.assertIn("S0", defs)
        for name in ("S1_05", "S2_10", "S3_15", "S4_05"):
            self.assertIn(name, defs)
        for shares in defs.values():
            self.assertAlmostEqual(sum(shares.values()), 1.0)
            self.assertTrue(all(0.0 <= s <= 1.0 for s in shares.values()))

    def test_evaluate_intervals(self):
        ranges = {ch: (0.0, 1e9) for ch in SPEND_COLUMNS}
        res = evaluate(fake_draws(), BUNDLE, 13000.0, dict(scenario_defs()["S0"]), 13, None, ranges)
        self.assertLessEqual(res["sales_lo"], res["sales_mean"])
        self.assertLessEqual(res["sales_mean"], res["sales_hi"])
        self.assertEqual(res["extrapolation_flags"], [])
        self.assertTrue(all(np.isfinite(v) for v in res["roas"].values()))

    def test_extrapolation_detected(self):
        ranges = {ch: (0.0, 10.0) for ch in SPEND_COLUMNS}
        res = evaluate(fake_draws(), BUNDLE, 13000.0, dict(scenario_defs()["S0"]), 13, None, ranges)
        self.assertTrue(res["extrapolation_flags"])

    def test_marginal_roas_finite(self):
        ranges = {ch: (0.0, 1e9) for ch in SPEND_COLUMNS}
        m = marginal_roas(
            fake_draws(), BUNDLE, 13000.0, dict(scenario_defs()["S0"]), 13, None, "mdsp_sem"
        )
        self.assertTrue(np.isfinite(m))


if __name__ == "__main__":
    unittest.main()
