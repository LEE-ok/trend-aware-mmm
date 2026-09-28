import importlib.util
import unittest

HAS_PYMC = importlib.util.find_spec("pymc") is not None


@unittest.skipUnless(HAS_PYMC, "pymc not installed")
class BayesianTests(unittest.TestCase):
    def test_fit_tiny(self):
        import numpy as np

        from trend_mmm.data.validation import SPEND_COLUMNS
        from trend_mmm.mmm.bayesian import (
            adstock_numpy,
            fit_bayesian,
            hill_numpy,
            predict_posterior_mean,
            summarize_posterior,
        )

        rng = np.random.default_rng(7)
        rows = []
        for i in range(15):
            rows.append(
                {
                    "spends": {ch: float(100 + 10 * i + j) for j, ch in enumerate(SPEND_COLUMNS)},
                    "sales": float(5000 + 50 * i + rng.normal()),
                }
            )
        idata, bundle = fit_bayesian(rows, SPEND_COLUMNS, draws=20, tune=20, chains=1)
        preds = predict_posterior_mean(idata, bundle, rows)
        self.assertEqual(len(preds), 15)
        self.assertTrue(all(np.isfinite(preds)))
        summary = summarize_posterior(idata, SPEND_COLUMNS)
        for ch in SPEND_COLUMNS:
            self.assertGreaterEqual(summary["params"][f"beta_{ch}"]["mean"], 0.0)
        self.assertEqual(
            list(adstock_numpy(np.array([10.0, 0.0]), 0.5)), [10.0, 5.0]
        )
        self.assertEqual(hill_numpy(np.array([0.0]), 1.0, 100.0)[0], 0.0)


if __name__ == "__main__":
    unittest.main()
