import unittest

import numpy as np

from trend_mmm.data.validation import SPEND_COLUMNS
from trend_mmm.optimization.allocate import (
    _params,
    channel_sales,
    draw_offsets,
    objective_value,
    optimize,
    optimize_draws,
    random_check,
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


class QuantileObjectiveTests(unittest.TestCase):
    def test_default_objective_is_unchanged(self):
        draws = make_draws()
        default, _ = optimize_draws(draws, BUNDLE, TOTAL, WEEKS, BOUNDS, pooled=True)
        explicit, _ = optimize_draws(draws, BUNDLE, TOTAL, WEEKS, BOUNDS, pooled=True, objective="mean")
        np.testing.assert_array_equal(default, explicit)

    def test_quantile_optimum_beats_mean_optimum_on_its_quantile(self):
        draws = make_draws(40, seed=1)
        params = _params(draws, BUNDLE)
        offset = draw_offsets(draws, WEEKS, None)
        mean_opt, _ = optimize_draws(draws, BUNDLE, TOTAL, WEEKS, BOUNDS, pooled=True)
        q_opt, _ = optimize_draws(
            draws, BUNDLE, TOTAL, WEEKS, BOUNDS, pooled=True, objective="quantile", q=0.1, offset=offset
        )
        np.testing.assert_allclose(q_opt.sum(), 1.0)
        self.assertTrue((q_opt <= 0.6 + 1e-9).all())
        q_at = lambda sh: objective_value(params, sh, TOTAL, WEEKS, "quantile", 0.1, offset)
        mean_at = lambda sh: objective_value(params, sh, TOTAL, WEEKS, "mean", offset=offset)
        self.assertGreaterEqual(q_at(q_opt[0]), q_at(mean_opt[0]) - 1e-6)
        self.assertGreaterEqual(mean_at(mean_opt[0]), mean_at(q_opt[0]) - 1e-6)

    def test_offsets_include_intercept_and_aux(self):
        draws = [{**d, "gamma": np.array([2.0, -1.0])} for d in make_draws(3)]
        np.testing.assert_allclose(draw_offsets(draws, WEEKS, [1.0, 1.0]), WEEKS * (1000.0 + 1.0))

    def test_bad_objective_rejected(self):
        with self.assertRaises(ValueError):
            optimize_draws(make_draws(2), BUNDLE, TOTAL, WEEKS, BOUNDS, pooled=True, objective="max")
        with self.assertRaises(ValueError):
            optimize_draws(make_draws(2), BUNDLE, TOTAL, WEEKS, BOUNDS, pooled=True, objective="quantile", q=1.0)


class RandomCheckTests(unittest.TestCase):
    def test_greedy_optimum_has_no_better_random_split(self):
        draws = make_draws()
        pooled, _ = optimize_draws(draws, BUNDLE, TOTAL, WEEKS, BOUNDS, pooled=True)
        res = random_check(draws, BUNDLE, TOTAL, WEEKS, BOUNDS, pooled[0], n=300, seed=7)
        self.assertEqual((res["n"], res["seed"]), (300, 7))
        self.assertEqual(res["n_better"], 0)
        self.assertLessEqual(res["max_improvement"], 1e-6)

    def test_bad_split_is_beaten_and_samples_respect_bounds(self):
        bounds = {**BOUNDS, CHS[0]: (0.1, 0.3)}
        worst = [0.3, 0.6, 0.1 / 3, 0.1 / 3, 0.1 / 3]  # feasible but far from the optimum
        res = random_check(make_draws(), BUNDLE, TOTAL, WEEKS, bounds, worst, n=200, seed=0)
        self.assertGreater(res["n_better"], 0)
        self.assertGreater(res["max_improvement"], 0)
        best = res["best_random_shares"]
        self.assertAlmostEqual(sum(best.values()), 1.0)
        self.assertTrue(0.1 - 1e-9 <= best[CHS[0]] <= 0.3 + 1e-9)
        self.assertTrue(all(v <= 0.6 + 1e-9 for v in best.values()))

    def test_same_seed_same_result(self):
        draws = make_draws()
        a = random_check(draws, BUNDLE, TOTAL, WEEKS, BOUNDS, [0.2] * 5, n=50, seed=3)
        b = random_check(draws, BUNDLE, TOTAL, WEEKS, BOUNDS, [0.2] * 5, n=50, seed=3)
        self.assertEqual(a, b)


if __name__ == "__main__":
    unittest.main()
