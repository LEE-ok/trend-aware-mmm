import unittest

from trend_mmm.mmm.baseline import adstock, fit_baseline, fit_ols, metrics, predict, saturate

CHANNELS = ("mdsp_dm", "mdsp_so")


def make_rows(n=40):
    rows = []
    for i in range(n):
        rows.append(
            {
                "spends": {"mdsp_dm": 100.0 + i * 5.0, "mdsp_so": 50.0 + (i % 7)},
                "sales": 1000.0 + i * 10.0,
            }
        )
    return rows


class BaselineTests(unittest.TestCase):
    def test_adstock_no_decay(self):
        self.assertEqual(adstock([1.0, 2.0, 3.0], 0.0), [1.0, 2.0, 3.0])

    def test_adstock_carryover(self):
        out = adstock([10.0, 0.0, 0.0], 0.5)
        self.assertAlmostEqual(out[0], 10.0)
        self.assertAlmostEqual(out[1], 5.0)
        self.assertAlmostEqual(out[2], 2.5)

    def test_saturate_bounds(self):
        vals = saturate([0.0, 50.0, 1e9], 1.0, 100.0)
        self.assertEqual(vals[0], 0.0)
        self.assertTrue(0.0 < vals[1] < 1.0)
        self.assertTrue(0.99 < vals[2] < 1.0)
        with self.assertRaises(ValueError):
            saturate([1.0], 1.0, 0.0)

    def test_ols_recovers_line(self):
        feats = [[float(i)] for i in range(10)]
        target = [3.0 + 2.0 * i for i in range(10)]
        coefs = fit_ols(feats, target)
        self.assertAlmostEqual(coefs[0], 3.0, places=6)
        self.assertAlmostEqual(coefs[1], 2.0, places=6)

    def test_fit_predict_metrics(self):
        rows = make_rows()
        model = fit_baseline(rows, CHANNELS, decays=(0.0, 0.5), alphas=(1.0,))
        preds = predict(model, rows, CHANNELS)
        self.assertEqual(len(preds), len(rows))
        m = metrics([r["sales"] for r in rows], preds)
        self.assertLess(m["mape"], 0.5)
        self.assertGreaterEqual(m["dir_acc"], 0.0)

    def test_metrics_perfect(self):
        m = metrics([100.0, 200.0, 300.0], [100.0, 200.0, 300.0])
        self.assertEqual(m["mape"], 0.0)
        self.assertEqual(m["rmse"], 0.0)
        self.assertEqual(m["dir_acc"], 1.0)


if __name__ == "__main__":
    unittest.main()
